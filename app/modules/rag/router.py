from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional

from app.modules.rag.schemas import (
    TextCleanRequest,
    BatchCleanRequest,
    TextChunkRequest,
    EmbedAndStoreRequest,
    BatchEmbedRequest,
    SearchQueryRequest,
    SearchResultItem,
    AnswerQueryRequest,
    AnswerResponse,
    PipelineStatusResponse
)
from app.modules.rag.service import rag_service
from app.modules.rag.embeddings import embedding_manager
from app.core.logging import logger


router = APIRouter(prefix="/rag", tags=["RAG Pipeline & Embeddings"])


@router.post("/clean", summary="Clean Raw Scraped Data")
async def clean_scraped_data(request: TextCleanRequest):
    """Clean raw scraped JSON files and store cleaned text in `data/processed`."""
    try:
        processed = await rag_service.clean_documents(
            doc_id=request.doc_id,
            remove_boilerplate=request.remove_boilerplate,
            min_paragraph_length=request.min_paragraph_length
        )
        return {
            "status": "success",
            "message": f"Successfully cleaned {len(processed)} documents.",
            "processed_count": len(processed)
        }
    except Exception as e:
        logger.error(f"Error in clean endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clean-all", summary="Batch Clean All Scraped Documents at Once")
async def clean_all_documents(request: BatchCleanRequest):
    """Clean all stored scraped JSON files in a single batch operation."""
    try:
        processed = await rag_service.clean_all_documents(
            remove_boilerplate=request.remove_boilerplate,
            min_paragraph_length=request.min_paragraph_length
        )
        return {
            "status": "success",
            "message": f"Successfully batch cleaned {len(processed)} documents.",
            "processed_count": len(processed)
        }
    except Exception as e:
        logger.error(f"Error in clean-all endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunk", summary="Run Recursive Character Chunking")
async def chunk_documents(request: TextChunkRequest):
    """Chunk processed documents into semantic chunks with recursive character splitting."""
    try:
        chunks = await rag_service.chunk_documents(doc_id=request.doc_id)
        return {
            "status": "success",
            "message": f"Successfully generated {len(chunks)} chunks.",
            "total_chunks": len(chunks)
        }
    except Exception as e:
        logger.error(f"Error in chunk endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed", summary="Generate Embeddings & Index in Vector Store")
async def embed_and_store_documents(request: EmbedAndStoreRequest):
    """Download (if needed) free `all-MiniLM-L6-v2` model, encode chunks, and store in vector database."""
    try:
        count = await rag_service.embed_and_store(
            doc_id=request.doc_id,
            batch_size=request.batch_size
        )
        return {
            "status": "success",
            "message": f"Successfully embedded and indexed {count} chunks.",
            "indexed_vectors_count": count
        }
    except Exception as e:
        logger.error(f"Error in embed endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunk-all", summary="Batch Chunk All Scraped Documents at Once")
async def chunk_all_documents():
    """Clean and chunk all stored scraped documents in a single batch operation."""
    try:
        chunks = await rag_service.chunk_all_documents()
        return {
            "status": "success",
            "message": f"Successfully chunked all documents into {len(chunks)} total chunks.",
            "total_chunks": len(chunks)
        }
    except Exception as e:
        logger.error(f"Error in chunk-all endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed-all", summary="Batch Embed and Index All Documents at Once")
async def embed_all_documents(request: BatchEmbedRequest):
    """Batch chunk all documents, generate embeddings for all chunks, and index in vector store at once."""
    try:
        count = await rag_service.embed_all_documents(batch_size=request.batch_size)
        return {
            "status": "success",
            "message": f"Successfully embedded and indexed {count} total chunks across all documents.",
            "indexed_vectors_count": count
        }
    except Exception as e:
        logger.error(f"Error in embed-all endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=List[SearchResultItem], summary="Semantic Vector Similarity Search")
async def search_vector_store(request: SearchQueryRequest):
    """Perform semantic cosine similarity search with LLM query reframing and hybrid keyword matching."""
    try:
        results = rag_service.search_similar(
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            reframe=request.reframe,
            temperature=request.temperature
        )
        return results
    except Exception as e:
        logger.error(f"Error in search endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/answer", response_model=AnswerResponse, summary="Grounded RAG Answer Generation")
async def generate_rag_answer(request: AnswerQueryRequest):
    """Synthesize an accurate, grounded natural language answer from retrieved knowledge base chunks using local LLM."""
    try:
        response = rag_service.generate_answer(
            query=request.query,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            reframe=request.reframe,
            temperature=request.temperature
        )
        return response
    except Exception as e:
        logger.error(f"Error in answer endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=PipelineStatusResponse, summary="Get Pipeline & Vector Store Status")
async def get_pipeline_status():
    """Get metrics on scraped docs, processed docs, chunks, vector store count, and embedding model cache status."""
    try:
        return rag_service.get_pipeline_status()
    except Exception as e:
        logger.error(f"Error in status endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

