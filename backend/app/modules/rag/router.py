"""
FastAPI router for the RAG pipeline endpoints.

Each endpoint:
- Logs the incoming request with key parameters
- Measures and logs wall-clock execution time
- Returns structured success/error responses
"""

import asyncio
import time
from typing import List

from fastapi import APIRouter, HTTPException

from app.core.logging import get_module_logger
from app.modules.rag.embeddings import embedding_manager
from app.modules.rag.schemas import (
    AnswerQueryRequest,
    AnswerResponse,
    BatchCleanRequest,
    BatchEmbedRequest,
    EmbedAndStoreRequest,
    PipelineStatusResponse,
    SearchQueryRequest,
    SearchResultItem,
    TextChunkRequest,
    TextCleanRequest,
)
from app.modules.rag.service import rag_service

logger = get_module_logger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG Pipeline & Embeddings"])


# ---------------------------------------------------------------------------
# Cleaning endpoints
# ---------------------------------------------------------------------------

@router.post("/clean", summary="Clean Raw Scraped Document(s)")
async def clean_scraped_documents(request: TextCleanRequest):
    """Clean raw scraped JSON files and write cleaned output to ``data/clean_data``."""
    logger.info(
        "[POST /rag/clean] doc_id=%s, remove_boilerplate=%s",
        request.doc_id or "all",
        request.remove_boilerplate,
    )
    start_time = time.perf_counter()
    try:
        cleaned_docs = await rag_service.clean_documents(
            doc_id=request.doc_id,
            remove_boilerplate=request.remove_boilerplate,
            min_paragraph_length=request.min_paragraph_length,
        )
        elapsed = round(time.perf_counter() - start_time, 3)
        logger.info("[POST /rag/clean] cleaned %d document(s) in %.3fs.", len(cleaned_docs), elapsed)
        return {
            "status": "success",
            "message": f"Successfully cleaned {len(cleaned_docs)} document(s).",
            "processed_count": len(cleaned_docs),
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        logger.error("[POST /rag/clean] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/clean-all", summary="Batch Clean All Scraped Documents")
async def clean_all_scraped_documents(request: BatchCleanRequest):
    """Batch-clean all stored scraped JSON files in a single operation."""
    logger.info("[POST /rag/clean-all] remove_boilerplate=%s", request.remove_boilerplate)
    start_time = time.perf_counter()
    try:
        cleaned_docs = await rag_service.clean_all_documents(
            remove_boilerplate=request.remove_boilerplate,
            min_paragraph_length=request.min_paragraph_length,
        )
        elapsed = round(time.perf_counter() - start_time, 3)
        logger.info("[POST /rag/clean-all] cleaned %d document(s) in %.3fs.", len(cleaned_docs), elapsed)
        return {
            "status": "success",
            "message": f"Successfully batch-cleaned {len(cleaned_docs)} document(s).",
            "processed_count": len(cleaned_docs),
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        logger.error("[POST /rag/clean-all] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Chunking endpoints
# ---------------------------------------------------------------------------

@router.post("/chunk", summary="Chunk Cleaned Document(s)")
async def chunk_cleaned_documents(request: TextChunkRequest):
    """Chunk cleaned documents into semantic text segments with recursive character splitting."""
    logger.info(
        "[POST /rag/chunk] doc_id=%s, chunk_size=%d, overlap=%d",
        request.doc_id or "all",
        request.chunk_size,
        request.chunk_overlap,
    )
    start_time = time.perf_counter()
    try:
        chunks = await rag_service.chunk_documents(doc_id=request.doc_id)
        elapsed = round(time.perf_counter() - start_time, 3)
        logger.info("[POST /rag/chunk] generated %d chunk(s) in %.3fs.", len(chunks), elapsed)
        return {
            "status": "success",
            "message": f"Successfully generated {len(chunks)} chunk(s).",
            "total_chunks": len(chunks),
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        logger.error("[POST /rag/chunk] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chunk-all", summary="Batch Clean and Chunk All Documents")
async def chunk_all_scraped_documents():
    """Clean and chunk ALL stored scraped documents in one combined batch operation."""
    logger.info("[POST /rag/chunk-all] starting combined clean+chunk batch.")
    start_time = time.perf_counter()
    try:
        chunks = await rag_service.chunk_all_documents()
        elapsed = round(time.perf_counter() - start_time, 3)
        logger.info("[POST /rag/chunk-all] generated %d chunk(s) in %.3fs.", len(chunks), elapsed)
        return {
            "status": "success",
            "message": f"Successfully chunked all documents into {len(chunks)} chunk(s).",
            "total_chunks": len(chunks),
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        logger.error("[POST /rag/chunk-all] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Embedding endpoints
# ---------------------------------------------------------------------------

@router.post("/embed", summary="Embed and Index Document(s) in Vector Store")
async def embed_and_store_documents(request: EmbedAndStoreRequest):
    """Generate embeddings with ``all-MiniLM-L6-v2`` and index in the vector store."""
    logger.info(
        "[POST /rag/embed] doc_id=%s, batch_size=%d",
        request.doc_id or "all",
        request.batch_size,
    )
    start_time = time.perf_counter()
    try:
        indexed_count = await rag_service.embed_and_store(
            doc_id=request.doc_id,
            batch_size=request.batch_size,
        )
        elapsed = round(time.perf_counter() - start_time, 3)
        logger.info("[POST /rag/embed] indexed %d vector(s) in %.3fs.", indexed_count, elapsed)
        return {
            "status": "success",
            "message": f"Successfully embedded and indexed {indexed_count} chunk(s).",
            "indexed_vector_count": indexed_count,
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        logger.error("[POST /rag/embed] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/embed-all", summary="Batch Embed and Index All Documents")
async def embed_all_scraped_documents(request: BatchEmbedRequest):
    """Clean, chunk, embed, and index ALL documents in one end-to-end batch operation."""
    logger.info("[POST /rag/embed-all] starting full pipeline batch (batch_size=%d).", request.batch_size)
    start_time = time.perf_counter()
    try:
        indexed_count = await rag_service.embed_all_documents(batch_size=request.batch_size)
        elapsed = round(time.perf_counter() - start_time, 3)
        logger.info("[POST /rag/embed-all] indexed %d vector(s) in %.3fs.", indexed_count, elapsed)
        return {
            "status": "success",
            "message": f"Successfully embedded and indexed {indexed_count} chunk(s) across all documents.",
            "indexed_vector_count": indexed_count,
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        logger.error("[POST /rag/embed-all] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Search & answer endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/search",
    response_model=List[SearchResultItem],
    summary="Semantic Vector Similarity Search",
)
async def search_vector_store(request: SearchQueryRequest):
    """Hybrid semantic + keyword search over indexed chunks.

    Supports optional LLM query reframing for improved recall on
    ambiguous or under-specified queries.
    """
    logger.info(
        "[POST /rag/search] query='%s', top_k=%d, threshold=%s, reframe=%s",
        request.query,
        request.top_k,
        request.score_threshold,
        request.reframe,
    )
    start_time = time.perf_counter()
    try:
        results = await asyncio.to_thread(
            rag_service.search_similar,
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            reframe=request.reframe,
            temperature=request.temperature,
        )
        elapsed = round(time.perf_counter() - start_time, 3)
        logger.info(
            "[POST /rag/search] returned %d result(s) in %.3fs for query='%s'.",
            len(results),
            elapsed,
            request.query,
        )
        return results
    except Exception as exc:
        logger.error("[POST /rag/search] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/answer",
    response_model=AnswerResponse,
    summary="Grounded RAG Answer Generation",
)
async def generate_rag_answer(request: AnswerQueryRequest):
    """Retrieve relevant context chunks and synthesise a grounded LLM answer.

    The answer is generated by the local Qwen2.5-0.5B-Instruct model using
    only facts present in the retrieved context (no hallucination).
    """
    logger.info(
        "[POST /rag/answer] query='%s', top_k=%d, threshold=%s, reframe=%s, max_tokens=%d",
        request.query,
        request.top_k,
        request.score_threshold,
        request.reframe,
        request.max_new_tokens,
    )
    start_time = time.perf_counter()
    try:
        response = await asyncio.to_thread(
            rag_service.generate_answer,
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            reframe=request.reframe,
            temperature=request.temperature,
            max_new_tokens=request.max_new_tokens,
        )
        elapsed = round(time.perf_counter() - start_time, 3)
        logger.info(
            "[POST /rag/answer] generated answer in %.3fs for query='%s'.",
            elapsed,
            request.query,
        )
        return response
    except Exception as exc:
        logger.error("[POST /rag/answer] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    summary="Pipeline & Vector Store Health Status",
)
async def get_pipeline_status():
    """Return file counts, vector store metrics, and model cache status for all pipeline stages."""
    logger.debug("[GET /rag/status] fetching pipeline status.")
    try:
        status_data = rag_service.get_pipeline_status()
        return PipelineStatusResponse(**status_data)
    except Exception as exc:
        logger.error("[GET /rag/status] failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
