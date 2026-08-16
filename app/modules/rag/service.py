"""
RAG pipeline service for CrawlRAG.

Orchestrates the full data pipeline:
    Raw scraped JSON
        → TextCleaner       (remove boilerplate, normalise whitespace)
        → RecursiveCharacterChunker (split into semantic chunks)
        → EmbeddingManager  (encode chunks with all-MiniLM-L6-v2)
        → VectorStore       (persist and search embeddings)
        → LLMManager        (generate grounded answers from retrieved context)
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
from app.modules.rag.schemas import SearchResultItem
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
    "You are a knowledgeable and helpful assistant. "
    "Answer the user's question directly and concisely using ONLY the facts "
    "present in the Context Information below.\n\n"
    "Rules:\n"
    "- Answer in plain, natural English — no code, no markdown symbols.\n"
    "- Do NOT use phrases like 'Based on the context', 'According to the text', "
    "  or 'As mentioned in the snippets'.\n"
    "- If the answer is present, state it clearly and completely.\n"
    "- If asking about a specific item (e.g. a book, product, or person), "
    "  include all available details (name, category, price, status, etc.).\n"
    "- If the user asks for a list, present it with clean bullet points.\n"
    "- Do NOT invent, guess, or hallucinate any facts not in the Context.\n"
    "- Do NOT apologise or refuse if the information is present.\n"
    "- Keep your answer focused and stop when you have answered the question."
)


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
        hybrid_scored_items: List[Dict[str, Any]] = []

        for chunk_index, chunk_metadata in enumerate(vector_store.chunk_metadata):
            base_semantic_score = float(similarity_scores[chunk_index]) if chunk_index < len(similarity_scores) else 0.0
            chunk_text_lower = chunk_metadata.get("text", "").lower()
            chunk_title_lower = chunk_metadata.get("title", "").lower()

            score_boost = 0.0

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
                "chunk_index": chunk_metadata.get("chunk_index", 0),
            })

        # Step 4: rank descending by hybrid score.
        hybrid_scored_items.sort(key=lambda item: item["score"], reverse=True)

        # Step 5: apply score threshold with graceful fallback.
        if score_threshold is not None:
            threshold_filtered = [
                item for item in hybrid_scored_items if item["score"] >= score_threshold
            ]
            # Graceful fallback: if nothing meets the threshold, return best matches anyway.
            filtered_items = threshold_filtered[:top_k] if threshold_filtered else hybrid_scored_items[:top_k]
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

    def generate_answer(
        self,
        query: str,
        top_k: int = settings.RETRIEVAL_TOP_K,
        score_threshold: Optional[float] = settings.RETRIEVAL_SCORE_THRESHOLD,
        reframe: bool = True,
        temperature: float = settings.LLM_TEMPERATURE,
        max_new_tokens: int = settings.LLM_MAX_NEW_TOKENS,
    ) -> Dict[str, Any]:
        """Retrieve relevant context chunks and synthesize a grounded LLM answer.

        Parameters
        ----------
        query:
            The user's natural language question.
        top_k:
            Number of context chunks to retrieve.
        score_threshold:
            Minimum similarity score for context chunks.
        reframe:
            Whether to reframe the query for improved retrieval.
        temperature:
            LLM sampling temperature.
        max_new_tokens:
            Maximum tokens to generate.

        Returns
        -------
        Dict with ``query``, ``answer``, and ``sources`` keys.
        """
        retrieval_start = time.perf_counter()

        retrieved_chunks = self.search_similar(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            reframe=reframe,
            temperature=temperature,
        )

        retrieval_elapsed = round(time.perf_counter() - retrieval_start, 3)
        logger.debug(
            "Retrieval: %d chunks in %.3fs (query='%s').",
            len(retrieved_chunks),
            retrieval_elapsed,
            query,
        )

        if not retrieved_chunks:
            logger.warning("No relevant context found for query: '%s'.", query)
            return {
                "query": query,
                "answer": (
                    "I could not find relevant information in the available data "
                    "to answer your question."
                ),
                "sources": [],
            }

        # Deduplicate chunks by chunk_id to avoid feeding identical text to the LLM.
        seen_chunk_ids: set = set()
        unique_chunks: List[SearchResultItem] = []
        for chunk in retrieved_chunks:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                unique_chunks.append(chunk)

        # Build context string with numbered source references.
        context_blocks = [
            f"Source [{index + 1}] ({chunk.title}):\n{chunk.text}"
            for index, chunk in enumerate(unique_chunks)
        ]
        context_text = "\n\n".join(context_blocks)

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

        logger.info(
            "Answer generated in %.3fs (retrieval=%.3fs, generation=%.3fs) for query='%s'.",
            retrieval_elapsed + generation_elapsed,
            retrieval_elapsed,
            generation_elapsed,
            query,
        )

        return {
            "query": query,
            "answer": cleaned_answer,
            "sources": unique_chunks,
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
