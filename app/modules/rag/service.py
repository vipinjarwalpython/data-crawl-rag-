import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import aiofiles
import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.modules.rag.cleaner import TextCleaner
from app.modules.rag.chunker import RecursiveCharacterChunker
from app.modules.rag.embeddings import embedding_manager
from app.modules.rag.vector_store import vector_store
from app.modules.rag.llm import llm_manager
from app.modules.rag.schemas import SearchResultItem


class RAGPipelineService:
    """Orchestrator for Data Cleaning, Recursive Chunking, Model Embedding, and Vector Indexing."""

    def __init__(self):
        self.scraped_dir = settings.BASE_DIR / settings.SCRAPED_DIR
        self.clean_data_dir = settings.BASE_DIR / settings.CLEAN_DATA_DIR
        self.clean_data_dir.mkdir(parents=True, exist_ok=True)
        self.chunked_data_dir = settings.BASE_DIR / settings.CHUNKED_DATA_DIR
        self.chunked_data_dir.mkdir(parents=True, exist_ok=True)
        self.chunker = RecursiveCharacterChunker(
            chunk_size=settings.DEFAULT_CHUNK_SIZE,
            chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP
        )

    async def clean_documents(
        self,
        doc_id: Optional[str] = None,
        remove_boilerplate: bool = True,
        min_paragraph_length: int = 20
    ) -> List[Dict[str, Any]]:
        """Clean raw scraped JSON files and store in data/clean_data."""
        processed_docs = []
        files = [self.scraped_dir / f"{doc_id}.json"] if doc_id else list(self.scraped_dir.glob("*.json"))

        for file_path in files:
            if not file_path.exists():
                continue
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)

                cleaned_data = TextCleaner.clean_document_dict(
                    data,
                    remove_boilerplate=remove_boilerplate,
                    min_paragraph_length=min_paragraph_length
                )

                # Save to clean_data dir
                out_path = self.clean_data_dir / file_path.name
                async with aiofiles.open(out_path, "w", encoding="utf-8") as out_f:
                    await out_f.write(json.dumps(cleaned_data, indent=2, ensure_ascii=False))

                processed_docs.append(cleaned_data)
                logger.info(f"Cleaned and saved document to clean_data: {file_path.name}")
            except Exception as e:
                logger.error(f"Error cleaning document {file_path.name}: {e}")

        return processed_docs

    async def clean_all_documents(
        self,
        remove_boilerplate: bool = True,
        min_paragraph_length: int = 20
    ) -> List[Dict[str, Any]]:
        """Batch clean all scraped documents in a single operation."""
        return await self.clean_documents(
            doc_id=None,
            remove_boilerplate=remove_boilerplate,
            min_paragraph_length=min_paragraph_length
        )

    async def chunk_documents(self, doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Chunk cleaned documents using Recursive Character Chunker."""
        all_chunks = []
        files = [self.clean_data_dir / f"{doc_id}.json"] if doc_id else list(self.clean_data_dir.glob("*.json"))

        for file_path in files:
            if not file_path.exists():
                # If clean file doesn't exist, try cleaning first
                await self.clean_documents(doc_id=file_path.stem)
            
            if not file_path.exists():
                continue

            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)

                d_id = data.get("id", file_path.stem)
                url = data.get("url", "")
                title = data.get("title", "Untitled")
                text_to_chunk = data.get("processed_text") or data.get("clean_text", "")

                chunks = self.chunker.chunk_document(d_id, url, title, text_to_chunk)
                all_chunks.extend(chunks)

                # Save chunks JSON file to chunked_data dir
                chunks_path = self.chunked_data_dir / f"{d_id}_chunks.json"
                async with aiofiles.open(chunks_path, "w", encoding="utf-8") as out_f:
                    await out_f.write(json.dumps(chunks, indent=2, ensure_ascii=False))

            except Exception as e:
                logger.error(f"Error chunking document {file_path.name}: {e}")

        return all_chunks

    async def embed_and_store(self, doc_id: Optional[str] = None, batch_size: int = 32) -> int:
        """Generate embeddings using all-MiniLM-L6-v2 and store in vector store."""
        chunks = await self.chunk_documents(doc_id)
        if not chunks:
            logger.warning("No chunks found to embed and store.")
            return 0

        texts = [chunk["text"] for chunk in chunks]
        logger.info(f"Generating embeddings for {len(texts)} chunks using {settings.DEFAULT_EMBEDDING_MODEL}...")

        # Run encoding in thread to prevent blocking event loop
        embeddings = await asyncio.to_thread(embedding_manager.encode, texts, batch_size)

        vector_store.add_embeddings(embeddings, chunks)
        logger.info(f"Successfully embedded and stored {len(chunks)} chunks into vector store.")
        return len(chunks)

    async def chunk_all_documents(self) -> List[Dict[str, Any]]:
        """Batch clean and chunk all scraped documents into chunked_data in a single operation."""
        await self.clean_all_documents()
        all_chunks = []
        files = list(self.clean_data_dir.glob("*.json"))

        for file_path in files:
            if not file_path.exists():
                continue
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)

                d_id = data.get("id", file_path.stem)
                url = data.get("url", "")
                title = data.get("title", "Untitled")
                text_to_chunk = data.get("processed_text") or data.get("clean_text", "")

                chunks = self.chunker.chunk_document(d_id, url, title, text_to_chunk)
                all_chunks.extend(chunks)

                chunks_path = self.chunked_data_dir / f"{d_id}_chunks.json"
                async with aiofiles.open(chunks_path, "w", encoding="utf-8") as out_f:
                    await out_f.write(json.dumps(chunks, indent=2, ensure_ascii=False))
            except Exception as e:
                logger.error(f"Error batch chunking document {file_path.name}: {e}")

        logger.info(f"Successfully batch chunked all documents to chunked_data. Total chunks: {len(all_chunks)}")
        return all_chunks

    async def embed_all_documents(self, batch_size: int = 32) -> int:
        """Batch chunk all documents and embed/index all chunks into vector store at once."""
        chunks = await self.chunk_all_documents()
        if not chunks:
            logger.warning("No chunks found for batch embedding.")
            return 0

        # Clear vector store for clean, deduplicated bulk indexing
        vector_store.clear()

        texts = [chunk["text"] for chunk in chunks]
        logger.info(f"Generating embeddings for {len(texts)} total chunks across all documents using {settings.DEFAULT_EMBEDDING_MODEL}...")

        embeddings = await asyncio.to_thread(embedding_manager.encode, texts, batch_size)
        vector_store.add_embeddings(embeddings, chunks)

        logger.info(f"Successfully embedded and indexed {len(chunks)} total chunks across all documents.")
        return len(chunks)

    def search_similar(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        reframe: bool = False,
        temperature: float = 0.2
    ) -> List[SearchResultItem]:
        """Search vector store for chunks semantically similar to query with LLM query reframing and hybrid keyword matching."""
        effective_query = query
        if reframe:
            try:
                effective_query = llm_manager.reframe_query(query)
            except Exception as e:
                logger.warning(f"Query reframing skipped: {e}")

        query_lower = effective_query.lower()
        original_lower = query.lower()
        
        # Combine keyword intent checks from both original and reframed query
        combined_query = f"{original_lower} {query_lower}"
        keyword_boost = any(kw in combined_query for kw in ["phone", "mobile", "number", "call", "contact", "email", "address", "location", "indore"])

        query_emb = embedding_manager.encode([effective_query])
        raw_results = vector_store.search(query_emb, top_k=top_k * 4, score_threshold=score_threshold)

        if keyword_boost:
            for item in raw_results:
                url = item.get("url", "").lower()
                text = item.get("text", "").lower()
                if "contact" in url and ("address" in text or "indore" in text or "+91" in text):
                    item["score"] += 0.60
                elif "+91" in text or "our address" in text or "indore" in text or "mailbox" in text:
                    item["score"] += 0.35
                elif "info@" in text or "contact" in url:
                    item["score"] += 0.15

            raw_results.sort(key=lambda x: x["score"], reverse=True)

        results = []
        for item in raw_results[:top_k]:
            results.append(SearchResultItem(
                chunk_id=item["chunk_id"],
                doc_id=item["doc_id"],
                url=item["url"],
                title=item["title"],
                text=item["text"],
                score=item["score"],
                chunk_index=item["chunk_index"]
            ))
        return results

    def generate_answer(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: Optional[float] = 0.3,
        reframe: bool = True,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """Perform semantic search and synthesize an accurate, grounded LLM answer using retrieved chunks."""
        sources = self.search_similar(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            reframe=reframe,
            temperature=temperature
        )

        if not sources:
            return {
                "query": query,
                "answer": "I couldn't find any relevant information in the company knowledge base to answer your question.",
                "sources": []
            }

        context_blocks = []
        for idx, item in enumerate(sources):
            context_blocks.append(f"Source [{idx+1}] (Title: {item.title} | URL: {item.url}):\n{item.text}")

        context_text = "\n\n".join(context_blocks)

        system_prompt = (
            "You are an expert AI knowledge assistant and corporate chatbot. "
            "Answer the user's question accurately, concisely, and professionally using ONLY the provided context snippets. "
            "Do not hallucinate or add external facts not present in the context. "
            "If the answer cannot be found in the context, state: 'I couldn't find relevant information in the company knowledge base to answer your question.'"
        )

        prompt = f"Context Information:\n{context_text}\n\nUser Question: {query}\n\nAccurate Answer:"

        answer = llm_manager.generate_response(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=300,
            temperature=temperature
        )

        return {
            "query": query,
            "answer": answer,
            "sources": sources
        }

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get summary metrics for scraping, cleaning, chunking, and vector store."""
        scraped_files = list(settings.SCRAPED_DIR.glob("*.json")) if settings.SCRAPED_DIR.exists() else []
        clean_files = list(settings.CLEAN_DATA_DIR.glob("*.json")) if settings.CLEAN_DATA_DIR.exists() else []
        chunk_files = list(settings.CHUNKED_DATA_DIR.glob("*.json")) if settings.CHUNKED_DATA_DIR.exists() else []

        return {
            "scraped_count": len(scraped_files),
            "clean_data_count": len(clean_files),
            "chunked_data_count": len(chunk_files),
            "vector_count": vector_store.count(),
            "embedding_model": settings.DEFAULT_EMBEDDING_MODEL,
            "model_cached_locally": embedding_manager.is_cached_locally()
        }


import asyncio
rag_service = RAGPipelineService()
