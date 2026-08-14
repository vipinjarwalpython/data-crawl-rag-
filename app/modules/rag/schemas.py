from typing import List, Optional
from pydantic import BaseModel, Field


class TextCleanRequest(BaseModel):
    """Request model for cleaning a specific document or batch."""
    doc_id: Optional[str] = Field(None, description="Specific document ID to clean. If omitted, cleans all scraped documents.")
    remove_boilerplate: bool = Field(True, description="Remove common cookie banners, footers, navigation junk.")
    min_paragraph_length: int = Field(20, description="Minimum character length for a text block to be retained.")


class BatchCleanRequest(BaseModel):
    """Request model for batch cleaning all scraped documents at once."""
    remove_boilerplate: bool = Field(True, description="Remove common cookie banners, footers, navigation junk.")
    min_paragraph_length: int = Field(20, description="Minimum character length for a text block to be retained.")


class TextChunkRequest(BaseModel):
    """Request model for recursive character chunking."""
    doc_id: Optional[str] = Field(None, description="Specific processed document ID to chunk. If omitted, chunks all processed documents.")
    chunk_size: int = Field(500, description="Maximum character length per chunk.")
    chunk_overlap: int = Field(50, description="Character overlap between consecutive chunks.")


class EmbedAndStoreRequest(BaseModel):
    """Request model for generating embeddings and upserting into vector store."""
    doc_id: Optional[str] = Field(None, description="Specific chunked document ID. If omitted, embeds all chunked documents.")
    batch_size: int = Field(32, description="Batch size for embedding generation.")


class BatchEmbedRequest(BaseModel):
    """Request model for batch embedding and indexing all documents at once."""
    batch_size: int = Field(32, description="Batch size for embedding generation.")


class SearchQueryRequest(BaseModel):
    """Request model for semantic vector similarity search."""
    query: str = Field(..., description="Natural language search query.")
    top_k: int = Field(5, description="Number of top matching chunks to return.")
    score_threshold: Optional[float] = Field(None, description="Minimum similarity score threshold (0.0 to 1.0).")
    reframe: bool = Field(False, description="Whether to reframe query using LLM for enhanced retrieval.")
    temperature: float = Field(0.2, description="Temperature for LLM generation (0.0 for deterministic, higher for creativity).")


class SearchResultItem(BaseModel):
    """Search result item matching user query."""
    chunk_id: str
    doc_id: str
    url: str
    title: str
    text: str
    score: float
    chunk_index: int


class AnswerQueryRequest(BaseModel):
    """Request model for RAG grounded answer generation."""
    query: str = Field(..., description="Natural language question.")
    top_k: int = Field(5, description="Number of top matching chunks to retrieve for context.")
    score_threshold: Optional[float] = Field(0.3, description="Minimum similarity score threshold.")
    reframe: bool = Field(True, description="Whether to reframe query using LLM for enhanced retrieval.")
    temperature: float = Field(0.2, description="Temperature for LLM generation.")


class AnswerResponse(BaseModel):
    """Response model containing grounded LLM answer and retrieved source chunks."""
    query: str
    answer: str
    sources: List[SearchResultItem]


class PipelineStatusResponse(BaseModel):
    """Status metrics for processing & vector store."""
    scraped_count: int
    clean_data_count: int
    chunked_data_count: int
    vector_count: int
    embedding_model: str
    model_cached_locally: bool
