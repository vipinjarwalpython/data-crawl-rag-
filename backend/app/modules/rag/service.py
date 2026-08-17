"""
RAG pipeline service for CrawlRAG.

Orchestrates the full data pipeline:
    Raw scraped JSON
        → TextCleaner               (remove boilerplate, normalise whitespace)
        → RecursiveCharacterChunker (split into semantic chunks)
        → EmbeddingManager          (encode chunks with BAAI/bge-small-en-v1.5)
        → VectorStore               (persist and search embeddings)
        → LLMManager                (generate grounded answers from retrieved context)

When the vector store cannot find relevant context for a query the pipeline
falls back to a structured PostgreSQL lookup:
    Query
        → NLToSQLConverter          (LLM converts question → safe SELECT SQL)
        → CarsRepository            (execute query against the `cars` table)
        → format answer from rows   (or return NO_CONTEXT_SENTINEL if empty)
"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import numpy as np

from app.core.config import settings
from app.core.logging import get_module_logger
from app.modules.rag.chunker import RecursiveCharacterChunker
from app.modules.rag.cleaner import TextCleaner
from app.modules.rag.embeddings import embedding_manager
from app.modules.rag.llm import llm_manager, llm_output_cleaner
from app.modules.database.nl_to_sql import nl_sql_converter
from app.modules.database.repository import cars_repository
from app.modules.rag.schemas import NO_CONTEXT_SENTINEL, SearchResultItem
from app.modules.rag.vector_store import vector_store

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Stop-words used during hybrid keyword scoring
# ---------------------------------------------------------------------------

_RETRIEVAL_STOP_WORDS = frozenset({
    "give", "info", "information", "about", "book", "books", "the", "a", "an",
    "what", "is", "are", "do", "you", "have", "in", "of", "to", "for", "me",
    "tell", "show", "please", "can", "could", "would", "get", "find", "i",
    "want", "need", "how", "many", "much", "list", "all",
})

# Boost weights used in hybrid scoring (calibrated to avoid overriding semantics).
_PHRASE_TEXT_BOOST = 0.40
_PHRASE_TITLE_BOOST = 0.25
_KEYWORD_SECTION_BOOST = 0.20
_KEYWORD_TEXT_BOOST = 0.10
_KEYWORD_TITLE_BOOST = 0.15
_CONTACT_EXACT_BOOST = 0.35
_CONTACT_PARTIAL_BOOST = 0.20

# Contact-intent trigger keywords.
_CONTACT_INTENT_KEYWORDS = frozenset({
    "contact", "phone", "email", "address", "call", "location",
})


# ---------------------------------------------------------------------------
# System prompt template for answer generation
# ---------------------------------------------------------------------------

_ANSWER_SYSTEM_PROMPT = (
    "You are a strict, grounded assistant that ONLY answers from the provided context.\n\n"
    "Rules:\n"
    "- Answer in plain, natural English — no code, no markdown symbols.\n"
    "- Use ONLY facts explicitly stated in the Context Information below.\n"
    "- Do NOT use phrases like 'Based on the context', 'According to the text', "
    "  or 'As mentioned in the snippets'.\n"
    "- If the answer is present, state it clearly and completely.\n"
    "- If asking about a specific item (e.g. a book, product, or person), "
    "  include all available details (name, category, price, status, etc.).\n"
    "- If the user asks for a list, present it with clean bullet points.\n"
    "- CRITICAL: If the Context Information does NOT contain enough information to "
    "  answer the question, respond with exactly: "
    "  'I don't have information about that in the available data.'\n"
    "- Do NOT draw on any general knowledge, training data, or outside facts — "
    "  even if you know the answer from general knowledge.\n"
    "- Do NOT invent, guess, or hallucinate any facts not in the Context.\n"
    "- Do NOT apologise or refuse if the information is present.\n"
    "- Keep your answer focused and stop when you have answered the question."
)


# ---------------------------------------------------------------------------
# PostgreSQL row formatter  (used by generate_answer's DB fallback)
# ---------------------------------------------------------------------------

def _format_db_rows_as_answer(rows: List[Dict[str, Any]]) -> str:
    """Convert PostgreSQL result rows into a human-readable answer string.

    A single row gets a detailed card layout; multiple rows get a bullet list.
    This output is returned directly as the ``answer`` field in the API response.
    """
    if not rows:
        return ""

    def _price(row: Dict[str, Any]) -> str:
        price = row.get("price_usd")
        return f"USD {float(price):,.0f}" if price is not None else "N/A"

    def _mileage(row: Dict[str, Any]) -> str:
        km = row.get("mileage_km")
        return f"{km:,} km" if km is not None else "N/A"

    if len(rows) == 1:
        car = rows[0]
        lines = [
            f"{car.get('brand', '?')} {car.get('model', '?')} ({car.get('year', 'N/A')})",
            f"  Status   : {car.get('status', 'N/A')}",
            f"  Category : {car.get('category', 'N/A')}",
            f"  Origin   : {car.get('country_of_origin', 'N/A')}",
            f"  Mileage  : {_mileage(car)}",
            f"  Price    : {_price(car)}",
        ]
        if car.get("description"):
            lines.append(f"  Notes    : {car['description']}")
        return "\n".join(lines)

    # Multiple rows — concise bullet list.
    header = f"Found {len(rows)} matching car(s):"
    bullets = [
        f"  • {r.get('brand', '?')} {r.get('model', '?')} "
        f"({r.get('year', '?')}) — {r.get('status', '?')} — {_price(r)}"
        for r in rows
    ]
    return "\n".join([header] + bullets)


def _detect_hallucinated_entities(cleaned_answer: str, context_text: str) -> List[str]:
    """Detect proper nouns, alphanumeric model names, or numbers in the answer

    that do not exist anywhere in the retrieved context text.
    """
    context_lower = context_text.lower()
    candidate_tokens = set(re.findall(r"\b[A-Z0-9][A-Za-z0-9\-]{1,15}\b", cleaned_answer))

    ignored = _RETRIEVAL_STOP_WORDS | {
        "The", "These", "This", "They", "There", "Here", "Price", "USD", "Source",
        "Available", "Reserved", "Sold", "Coupe", "Sedan", "Convertible", "Hatchback",
        "Year", "Mileage", "Country", "Origin", "Direct", "Answer", "According", "Information",
        "List", "Listings", "Only", "Priced", "Above", "Cost", "Costing", "Given", "Found",
        "Matching", "Notes", "Status", "Category"
    }

    hallucinated = []
    for token in candidate_tokens:
        if token in ignored or token.isdigit():
            continue
        if token.lower() not in context_lower:
            hallucinated.append(token)

    return hallucinated



# ---------------------------------------------------------------------------
# RAG Pipeline Service
# ---------------------------------------------------------------------------

class RAGPipelineService:
    """Orchestrator for the full RAG data pipeline.

    Provides high-level async methods for each pipeline stage
    (clean → chunk → embed → search → answer) as well as combined
    batch operations.
    """

    def __init__(self) -> None:
        self.scraped_dir: Path = settings.resolve_path(settings.SCRAPED_DIR)
        self.clean_data_dir: Path = settings.resolve_path(settings.CLEAN_DATA_DIR)
        self.chunked_data_dir: Path = settings.resolve_path(settings.CHUNKED_DATA_DIR)

        self.clean_data_dir.mkdir(parents=True, exist_ok=True)
        self.chunked_data_dir.mkdir(parents=True, exist_ok=True)

        self.chunker = RecursiveCharacterChunker(
            chunk_size=settings.DEFAULT_CHUNK_SIZE,
            chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP,
        )

    # ------------------------------------------------------------------
    # Stage 1: Cleaning
    # ------------------------------------------------------------------

    async def clean_documents(
        self,
        doc_id: Optional[str] = None,
        remove_boilerplate: bool = True,
        min_paragraph_length: int = 20,
    ) -> List[Dict[str, Any]]:
        """Clean raw scraped JSON files and save results to ``data/clean_data``.

        Parameters
        ----------
        doc_id:
            When provided, only the document with this ID is cleaned.
            When ``None``, all scraped documents are cleaned.
        remove_boilerplate:
            Strip cookie notices, navigation junk, and footer noise.
        min_paragraph_length:
            Minimum character count for a text block to be retained.

        Returns
        -------
        List of cleaned document dicts.
        """
        target_files: List[Path] = (
            [self.scraped_dir / f"{doc_id}.json"]
            if doc_id
            else sorted(self.scraped_dir.glob("*.json"))
        )

        cleaned_documents: List[Dict[str, Any]] = []
        stage_start = time.perf_counter()

        for source_file in target_files:
            if not source_file.exists():
                logger.warning("Scraped file not found, skipping: '%s'.", source_file)
                continue
            try:
                async with aiofiles.open(source_file, "r", encoding="utf-8") as file_handle:
                    raw_content = await file_handle.read()
                document_data: Dict[str, Any] = json.loads(raw_content)

                cleaned_document = TextCleaner.clean_document_dict(
                    document_data,
                    remove_boilerplate=remove_boilerplate,
                    min_paragraph_length=min_paragraph_length,
                )

                output_path = self.clean_data_dir / source_file.name
                async with aiofiles.open(output_path, "w", encoding="utf-8") as out_file:
                    await out_file.write(json.dumps(cleaned_document, indent=2, ensure_ascii=False))

                cleaned_documents.append(cleaned_document)
                logger.info("Cleaned document → '%s'.", source_file.name)

            except json.JSONDecodeError as exc:
                logger.error("Invalid JSON in '%s': %s", source_file.name, exc)
            except Exception as exc:
                logger.error(
                    "Error cleaning document '%s': %s",
                    source_file.name,
                    exc,
                    exc_info=True,
                )

        elapsed = round(time.perf_counter() - stage_start, 3)
        logger.info(
            "Cleaning stage complete: %d/%d documents processed in %.3fs.",
            len(cleaned_documents),
            len(target_files),
            elapsed,
        )
        return cleaned_documents

    async def clean_all_documents(
        self,
        remove_boilerplate: bool = True,
        min_paragraph_length: int = 20,
    ) -> List[Dict[str, Any]]:
        """Batch-clean all scraped documents in a single operation."""
        return await self.clean_documents(
            doc_id=None,
            remove_boilerplate=remove_boilerplate,
            min_paragraph_length=min_paragraph_length,
        )

    # ------------------------------------------------------------------
    # Stage 2: Chunking
    # ------------------------------------------------------------------

    async def _load_and_chunk_clean_file(
        self,
        clean_file_path: Path,
    ) -> List[Dict[str, Any]]:
        """Load a single cleaned JSON file and return its structured chunks.

        This private helper eliminates the duplicated chunking logic that
        previously appeared in both ``chunk_documents`` and ``chunk_all_documents``.
        """
        try:
            async with aiofiles.open(clean_file_path, "r", encoding="utf-8") as file_handle:
                raw_content = await file_handle.read()
            document_data: Dict[str, Any] = json.loads(raw_content)

            doc_id: str = document_data.get("id", clean_file_path.stem)
            source_url: str = document_data.get("url", "")
            page_title: str = document_data.get("title", "Untitled")
            full_text: str = (
                document_data.get("processed_text") or document_data.get("clean_text", "")
            )

            chunks = self.chunker.chunk_document(
                doc_id=doc_id,
                source_url=source_url,
                page_title=page_title,
                full_text=full_text,
            )

            # Persist chunks JSON file.
            chunks_output_path = self.chunked_data_dir / f"{doc_id}_chunks.json"
            async with aiofiles.open(chunks_output_path, "w", encoding="utf-8") as out_file:
                await out_file.write(json.dumps(chunks, indent=2, ensure_ascii=False))

            logger.debug(
                "Chunked '%s' → %d chunks saved to '%s'.",
                clean_file_path.name,
                len(chunks),
                chunks_output_path.name,
            )
            return chunks

        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in '%s': %s", clean_file_path.name, exc)
            return []
        except Exception as exc:
            logger.error(
                "Error chunking document '%s': %s",
                clean_file_path.name,
                exc,
                exc_info=True,
            )
            return []

    async def chunk_documents(
        self,
        doc_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Chunk cleaned documents into structured, overlapping text segments.

        Parameters
        ----------
        doc_id:
            When provided, only the document with this ID is chunked.
            When ``None``, all documents in ``data/clean_data`` are chunked.
        """
        if doc_id:
            clean_file_path = self.clean_data_dir / f"{doc_id}.json"
            if not clean_file_path.exists():
                logger.info("Clean file missing for '%s' — running cleaning first.", doc_id)
                await self.clean_documents(doc_id=doc_id)
            return await self._load_and_chunk_clean_file(clean_file_path)

        all_chunks: List[Dict[str, Any]] = []
        clean_files = sorted(self.clean_data_dir.glob("*.json"))
        stage_start = time.perf_counter()

        for clean_file_path in clean_files:
            file_chunks = await self._load_and_chunk_clean_file(clean_file_path)
            all_chunks.extend(file_chunks)

        elapsed = round(time.perf_counter() - stage_start, 3)
        logger.info(
            "Chunking stage complete: %d total chunks from %d files in %.3fs.",
            len(all_chunks),
            len(clean_files),
            elapsed,
        )
        return all_chunks

    async def chunk_all_documents(self) -> List[Dict[str, Any]]:
        """Clean and chunk all scraped documents in one combined batch operation."""
        await self.clean_all_documents()
        return await self.chunk_documents()

    # ------------------------------------------------------------------
    # Stage 3: Embedding & Indexing
    # ------------------------------------------------------------------

    async def embed_and_store(
        self,
        doc_id: Optional[str] = None,
        batch_size: int = 32,
    ) -> int:
        """Generate embeddings and store in the vector store.

        Parameters
        ----------
        doc_id:
            When provided, only that document is processed.
        batch_size:
            Number of texts encoded per batch.

        Returns
        -------
        Number of chunks indexed.
        """
        chunks = await self.chunk_documents(doc_id=doc_id)
        if not chunks:
            logger.warning("No chunks available to embed for doc_id='%s'.", doc_id)
            return 0

        chunk_texts = [chunk["text"] for chunk in chunks]
        logger.info(
            "Generating embeddings for %d chunks (model: %s) …",
            len(chunk_texts),
            settings.DEFAULT_EMBEDDING_MODEL,
        )

        stage_start = time.perf_counter()
        # Run CPU-intensive encoding in a thread to avoid blocking the event loop.
        embeddings = await asyncio.to_thread(
            embedding_manager.encode, chunk_texts, batch_size
        )
        elapsed = round(time.perf_counter() - stage_start, 3)

        vector_store.add_embeddings(embeddings, chunks)
        logger.info(
            "Embedding stage complete: %d chunks indexed in %.3fs.",
            len(chunks),
            elapsed,
        )
        return len(chunks)

    async def embed_all_documents(self, batch_size: int = 32) -> int:
        """Clean, chunk, embed, and index ALL documents from scratch.

        The vector store is cleared first to prevent stale or duplicate entries.
        """
        chunks = await self.chunk_all_documents()
        if not chunks:
            logger.warning("No chunks found for batch embedding.")
            return 0

        # Full rebuild — clear first to guarantee a clean, deduplicated index.
        vector_store.clear()

        chunk_texts = [chunk["text"] for chunk in chunks]
        logger.info(
            "Generating embeddings for %d total chunks across all documents …",
            len(chunk_texts),
        )

        stage_start = time.perf_counter()
        embeddings = await asyncio.to_thread(
            embedding_manager.encode, chunk_texts, batch_size
        )
        elapsed = round(time.perf_counter() - stage_start, 3)

        vector_store.add_embeddings(embeddings, chunks)
        logger.info(
            "Batch embedding complete: %d chunks indexed in %.3fs.",
            len(chunks),
            elapsed,
        )
        return len(chunks)

    # ------------------------------------------------------------------
    # Stage 4: Retrieval
    # ------------------------------------------------------------------

    def search_similar(
        self,
        query: str,
        top_k: int = settings.RETRIEVAL_TOP_K,
        score_threshold: Optional[float] = settings.RETRIEVAL_SCORE_THRESHOLD,
        reframe: bool = False,
        temperature: float = settings.LLM_TEMPERATURE,
    ) -> List[SearchResultItem]:
        """Search the vector store for chunks semantically similar to *query*.

        Uses a hybrid scoring strategy:
        1. Dense semantic score (cosine similarity of L2-normalised embeddings).
        2. Sparse keyword / phrase boost on chunk text and title.
        3. Optional LLM query reframing for improved recall on ambiguous queries.

        Parameters
        ----------
        query:
            Natural language search query.
        top_k:
            Maximum number of results to return.
        score_threshold:
            Minimum hybrid score to include a result.  Falls back to top result
            if nothing exceeds the threshold.
        reframe:
            Reframe the query with the LLM before retrieval.
        temperature:
            Temperature passed to the LLM for query reframing.
        """
        if vector_store.count() == 0:
            logger.warning("Vector store is empty. Please run /embed-all first.")
            return []

        query_stripped = query.strip()

        # Step 1: encode the original query.
        original_embedding = embedding_manager.encode([query_stripped])
        similarity_scores: np.ndarray = vector_store.compute_cosine_similarities(
            original_embedding
        )

        # Step 1b (optional): reframe and take element-wise maximum of scores.
        if reframe:
            try:
                reframed_query = llm_manager.reframe_query_for_retrieval(query_stripped)
                if reframed_query.lower() != query_stripped.lower():
                    logger.info("Using reframed query for retrieval: '%s'.", reframed_query)
                    reframed_embedding = embedding_manager.encode([reframed_query])
                    reframed_scores = vector_store.compute_cosine_similarities(reframed_embedding)
                    similarity_scores = np.maximum(similarity_scores, reframed_scores)
            except Exception as exc:
                logger.warning("Query reframing skipped: %s.", exc)

        # Step 2: extract meaningful keywords from the query.
        query_lower = query_stripped.lower()
        keyword_tokens = [
            token
            for token in re.findall(r"\b\w+\b", query_lower)
            if token not in _RETRIEVAL_STOP_WORDS and len(token) > 1
        ]
        keyword_phrases: List[str] = []
        if len(keyword_tokens) >= 2:
            keyword_phrases.append(" ".join(keyword_tokens))
        cleaned_phrase = " ".join(
            token for token in re.sub(r"[^\w\s]", "", query_lower).split()
            if token not in _RETRIEVAL_STOP_WORDS
        )
        if cleaned_phrase and cleaned_phrase not in keyword_phrases and len(cleaned_phrase.split()) >= 2:
            keyword_phrases.append(cleaned_phrase)

        # Detect contact-information intent.
        has_contact_intent = bool(_CONTACT_INTENT_KEYWORDS & set(keyword_tokens))

        # Step 3: compute hybrid scores for every chunk.
        # HALLUCINATION GUARD: only chunks with a meaningful base semantic score
        # (>= 0.10) are eligible for keyword boosting. This prevents a chunk that
        # is semantically unrelated from floating to the top purely on keyword matches.
        _MIN_BASE_SCORE_FOR_BOOST = 0.10
        hybrid_scored_items: List[Dict[str, Any]] = []

        for chunk_index, chunk_metadata in enumerate(vector_store.chunk_metadata):
            base_semantic_score = float(similarity_scores[chunk_index]) if chunk_index < len(similarity_scores) else 0.0
            chunk_text_lower = chunk_metadata.get("text", "").lower()
            chunk_title_lower = chunk_metadata.get("title", "").lower()

            score_boost = 0.0

            # Only apply keyword boosts when the chunk has at least a weak semantic
            # signal — this stops completely unrelated chunks from being promoted.
            if base_semantic_score >= _MIN_BASE_SCORE_FOR_BOOST:
                # Exact multi-word phrase match boost.
                for phrase in keyword_phrases:
                    if phrase in chunk_text_lower:
                        score_boost += _PHRASE_TEXT_BOOST
                    if phrase in chunk_title_lower:
                        score_boost += _PHRASE_TITLE_BOOST

                # Per-keyword match boost.
                for keyword in keyword_tokens:
                    escaped_keyword = re.escape(keyword)
                    if re.search(rf"\b{escaped_keyword}\b", chunk_text_lower):
                        # Section header match gets a stronger boost.
                        if f"### {keyword}" in chunk_text_lower or f"# {keyword}" in chunk_text_lower:
                            score_boost += _KEYWORD_SECTION_BOOST
                        else:
                            score_boost += _KEYWORD_TEXT_BOOST
                    if re.search(rf"\b{escaped_keyword}\b", chunk_title_lower):
                        score_boost += _KEYWORD_TITLE_BOOST

                # Contact-intent boost (calibrated to not completely override semantics).
                if has_contact_intent:
                    chunk_url_lower = chunk_metadata.get("url", "").lower()
                    if "contact" in chunk_url_lower and (
                        "address" in chunk_text_lower
                        or "+91" in chunk_text_lower
                    ):
                        score_boost += _CONTACT_EXACT_BOOST
                    elif "+91" in chunk_text_lower or "our address" in chunk_text_lower:
                        score_boost += _CONTACT_PARTIAL_BOOST

            hybrid_score = base_semantic_score + score_boost
            hybrid_scored_items.append({
                "chunk_id": chunk_metadata["chunk_id"],
                "doc_id": chunk_metadata["doc_id"],
                "url": chunk_metadata["url"],
                "title": chunk_metadata["title"],
                "text": chunk_metadata["text"],
                "score": round(hybrid_score, 4),
                "base_semantic_score": round(base_semantic_score, 4),
                "chunk_index": chunk_metadata.get("chunk_index", 0),
            })

        # Step 4: rank descending by hybrid score.
        hybrid_scored_items.sort(key=lambda item: item["score"], reverse=True)

        # Step 5: apply score threshold — NO fallback.
        # HALLUCINATION FIX: The old code had a "graceful fallback" that returned
        # results even when NOTHING exceeded the threshold. This meant out-of-context
        # queries always received irrelevant chunks, causing the LLM to hallucinate.
        # If nothing passes the threshold, we return an empty list so the caller can
        # correctly tell the user there is no relevant information.
        if score_threshold is not None:
            filtered_items = [
                item for item in hybrid_scored_items if item["score"] >= score_threshold
            ][:top_k]
        else:
            filtered_items = hybrid_scored_items[:top_k]

        return [
            SearchResultItem(
                chunk_id=item["chunk_id"],
                doc_id=item["doc_id"],
                url=item["url"],
                title=item["title"],
                text=item["text"],
                score=item["score"],
                chunk_index=item["chunk_index"],
            )
            for item in filtered_items
        ]

    # ------------------------------------------------------------------
    # Stage 5: Answer Generation
    # ------------------------------------------------------------------

    async def generate_answer(
        self,
        query: str,
        top_k: int = settings.RETRIEVAL_TOP_K,
        score_threshold: Optional[float] = settings.RETRIEVAL_SCORE_THRESHOLD,
        reframe: bool = True,
        temperature: float = settings.LLM_TEMPERATURE,
        max_new_tokens: int = settings.LLM_MAX_NEW_TOKENS,
    ) -> Dict[str, Any]:
        """Unified 2-tier search & answer generation endpoint.

        1. Vector Store Search: Dense vector + keyword hybrid search.
           If relevant chunks exist, generates a grounded answer with Qwen LLM.
        2. PostgreSQL Database Fallback: If vector search misses or has weak coverage,
           converts natural language question to SQL SELECT query against PostgreSQL table.
        3. Graceful Sentinel Response: If neither vector store nor PostgreSQL has data,
           returns clean "I don't have information about that in the available data."
           response with sources: [].
        """
        retrieval_start = time.perf_counter()

        # ------------------------------------------------------------------
        # Tier 1: Vector Store Search
        # ------------------------------------------------------------------
        retrieved_chunks = self.search_similar(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            reframe=reframe,
            temperature=temperature,
        )

        retrieval_elapsed = round(time.perf_counter() - retrieval_start, 3)
        logger.debug(
            "Vector retrieval: %d chunks in %.3fs (query='%s').",
            len(retrieved_chunks),
            retrieval_elapsed,
            query,
        )

        # Helper for PostgreSQL fallback (Tier 2)
        async def _run_postgres_fallback(reason: str) -> Dict[str, Any]:
            logger.info(
                "Triggering PostgreSQL Fallback for query='%s' (Reason: %s).",
                query,
                reason,
            )
            db_answer: Optional[str] = None
            try:
                # Step A: NL -> SQL SELECT query
                generated_sql = nl_sql_converter.convert(query)
                if generated_sql:
                    db_rows = await cars_repository.execute_safe_select(generated_sql)
                    if db_rows:
                        db_answer = _format_db_rows_as_answer(db_rows)
                        logger.info("PostgreSQL Fallback: SQL returned %d row(s).", len(db_rows))

                # Step B: Keyword fallback if SQL returned no rows
                if db_answer is None:
                    keywords = [w for w in query.split() if len(w) > 3]
                    keyword = max(keywords, key=len, default="")
                    if keyword:
                        kw_rows = await cars_repository.search_cars_by_keyword(keyword)
                        if kw_rows:
                            db_answer = _format_db_rows_as_answer(kw_rows)
                            logger.info("PostgreSQL Fallback: Keyword search returned %d row(s).", len(kw_rows))
            except Exception as db_exc:
                logger.warning("PostgreSQL Fallback exception: %s", db_exc)

            final_answer = db_answer or NO_CONTEXT_SENTINEL
            total_elapsed = round((time.perf_counter() - retrieval_start) * 1000, 2)

            return {
                "query": query,
                "answer": final_answer,
                "sources": [],
                "evaluation": {
                    "retrieval_confidence": 0.0,
                    "context_coverage": 0.0,
                    "faithfulness_score": 1.0 if db_answer is None else 0.0,
                    "retrieval_time_ms": round(retrieval_elapsed * 1000, 2),
                    "generation_time_ms": 0.0,
                    "total_time_ms": total_elapsed,
                },
            }

        # If vector store returned zero chunks, fallback to PostgreSQL immediately
        if not retrieved_chunks:
            return await _run_postgres_fallback("No vector chunks passed score threshold")

        # Deduplicate chunks by chunk_id
        seen_chunk_ids: set = set()
        unique_chunks: List[SearchResultItem] = []
        for chunk in retrieved_chunks:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                unique_chunks.append(chunk)

        # Build context text
        context_blocks = [
            f"Source [{index + 1}] ({chunk.title}):\n{chunk.text}"
            for index, chunk in enumerate(unique_chunks)
        ]
        context_text = "\n\n".join(context_blocks)
        context_lower = context_text.lower()

        # Compute query term coverage across vector context
        stop_words = _RETRIEVAL_STOP_WORDS
        query_words = {
            w.lower() for w in re.findall(r"\w+", query)
            if w.lower() not in stop_words and len(w) > 2
        }
        if query_words:
            matched_query_words = sum(1 for w in query_words if w in context_lower)
            context_coverage = round(matched_query_words / len(query_words), 4)
        else:
            context_coverage = 1.0

        # Pre-LLM Guard: If vector context coverage is weak (< 0.40), fallback to PostgreSQL
        _MIN_PRE_CONTEXT_COVERAGE = 0.40
        if context_coverage < _MIN_PRE_CONTEXT_COVERAGE:
            return await _run_postgres_fallback(
                f"Weak vector context coverage ({context_coverage:.4f} < {_MIN_PRE_CONTEXT_COVERAGE})"
            )

        # Generate answer with LLM using grounded vector context
        generation_prompt = (
            f"Context Information:\n{context_text}\n\n"
            f"Question: {query}\n\n"
            f"Direct Answer:"
        )

        generation_start = time.perf_counter()
        raw_answer = llm_manager.generate_response(
            prompt=generation_prompt,
            system_prompt=_ANSWER_SYSTEM_PROMPT,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
        )
        generation_elapsed = round(time.perf_counter() - generation_start, 3)

        cleaned_answer = llm_output_cleaner.clean(raw_answer)

        # Check sentinel detection
        answer_is_out_of_context = NO_CONTEXT_SENTINEL.lower() in cleaned_answer.lower()
        if answer_is_out_of_context:
            return await _run_postgres_fallback("LLM produced sentinel phrase (no vector info)")

        # Evaluate answer faithfulness
        answer_words = {
            w.lower() for w in re.findall(r"\w+", cleaned_answer)
            if w.lower() not in stop_words and len(w) > 2
        }
        if answer_words:
            supported_answer_words = sum(1 for w in answer_words if w in context_lower)
            faithfulness_score = round(supported_answer_words / len(answer_words), 4)
        else:
            faithfulness_score = 1.0

        # Post-LLM Anti-Hallucination Guard: detect ungrounded model codes or entities
        hallucinated_entities = _detect_hallucinated_entities(cleaned_answer, context_text)
        _FAITHFULNESS_HALLUCINATION_THRESHOLD = 0.05

        if (hallucinated_entities or faithfulness_score < _FAITHFULNESS_HALLUCINATION_THRESHOLD) and unique_chunks:
            logger.warning(
                "Post-generation anti-hallucination guard triggered for query='%s'. Hallucinated terms: %s. Fallback to PostgreSQL.",
                query,
                hallucinated_entities,
            )
            return await _run_postgres_fallback(
                f"Post-LLM hallucination detected (terms: {hallucinated_entities})"
            )

        # Successful grounded vector answer
        retrieval_confidence = round(sum(c.score for c in unique_chunks) / len(unique_chunks), 4)
        evaluation_metrics = {
            "retrieval_confidence": retrieval_confidence,
            "context_coverage": context_coverage,
            "faithfulness_score": faithfulness_score,
            "retrieval_time_ms": round(retrieval_elapsed * 1000, 2),
            "generation_time_ms": round(generation_elapsed * 1000, 2),
            "total_time_ms": round((retrieval_elapsed + generation_elapsed) * 1000, 2),
        }

        logger.info(
            "Vector answer generated in %.3fs for query='%s'.",
            retrieval_elapsed + generation_elapsed,
            query,
        )

        return {
            "query": query,
            "answer": cleaned_answer,
            "sources": unique_chunks,
            "evaluation": evaluation_metrics,
        }

    # ------------------------------------------------------------------
    # Pipeline status
    # ------------------------------------------------------------------

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Return counts and health metrics for all pipeline stages."""
        scraped_file_count = len(list(self.scraped_dir.glob("*.json"))) if self.scraped_dir.exists() else 0
        cleaned_file_count = len(list(self.clean_data_dir.glob("*.json"))) if self.clean_data_dir.exists() else 0
        chunked_file_count = len(list(self.chunked_data_dir.glob("*.json"))) if self.chunked_data_dir.exists() else 0

        return {
            "scraped_document_count": scraped_file_count,
            "cleaned_document_count": cleaned_file_count,
            "chunked_document_count": chunked_file_count,
            "vector_count": vector_store.count(),
            "embedding_dimension": settings.EMBEDDING_DIMENSION,
            "embedding_model": settings.DEFAULT_EMBEDDING_MODEL,
            "embedding_model_cached_locally": embedding_manager.is_cached_locally(),
            "llm_model": settings.DEFAULT_LLM_MODEL,
            "llm_model_cached_locally": llm_manager.is_cached_locally(),
            "vector_store_stats": vector_store.get_stats(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
rag_service = RAGPipelineService()
