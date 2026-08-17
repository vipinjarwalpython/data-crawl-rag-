"""
Pydantic request/response schemas for the RAG pipeline endpoints.

Design notes:
- QueryNormalizerMixin is shared by all query schemas to avoid duplicating
  the ``normalize_input`` validator.
- Default thresholds and counts are pulled from ``settings`` so that tuning
  one value in .env affects all endpoints at once.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field, model_validator

from app.core.config import settings


# ---------------------------------------------------------------------------
# Shared mixin
# ---------------------------------------------------------------------------

class QueryNormalizerMixin(BaseModel):
    """Normalises the incoming ``query`` field from common alternative keys.

    Accepts ``question``, ``prompt``, ``q``, ``input``, or ``text`` as
    aliases for ``query`` so that callers do not need to know the exact
    field name.
    """

    @model_validator(mode="before")
    @classmethod
    def _normalise_query_field(cls, raw_data: Any) -> Any:
        """Remap alternative query-field names to ``query`` before validation."""
        if not isinstance(raw_data, dict):
            return raw_data

        if not raw_data.get("query"):
            for alternative_key in ("question", "prompt", "q", "input", "text"):
                if raw_data.get(alternative_key):
                    raw_data["query"] = raw_data[alternative_key]
                    break

        return raw_data


# ---------------------------------------------------------------------------
# Cleaning / chunking / embedding request schemas
# ---------------------------------------------------------------------------

class TextCleanRequest(BaseModel):
    """Request body for cleaning a single document or all scraped documents."""

    doc_id: Optional[str] = Field(
        default=None,
        description="Target document ID.  Omit to clean all scraped documents.",
    )
    remove_boilerplate: bool = Field(
        default=True,
        description="Strip cookie banners, nav noise, footers, and tracking text.",
    )
    min_paragraph_length: int = Field(
        default=20,
        ge=0,
        description="Minimum character length for a text block to be retained.",
    )


class BatchCleanRequest(BaseModel):
    """Request body for batch-cleaning all scraped documents at once."""

    remove_boilerplate: bool = Field(default=True, description="Strip boilerplate noise.")
    min_paragraph_length: int = Field(
        default=20,
        ge=0,
        description="Minimum character length for a text block to be retained.",
    )


class TextChunkRequest(BaseModel):
    """Request body for recursive character chunking."""

    doc_id: Optional[str] = Field(
        default=None,
        description="Target document ID.  Omit to chunk all cleaned documents.",
    )
    chunk_size: int = Field(
        default=settings.DEFAULT_CHUNK_SIZE,
        ge=100,
        le=2000,
        description="Maximum character length per chunk.",
    )
    chunk_overlap: int = Field(
        default=settings.DEFAULT_CHUNK_OVERLAP,
        ge=0,
        le=500,
        description="Character overlap between consecutive chunks.",
    )


class EmbedAndStoreRequest(BaseModel):
    """Request body for embedding a specific (or all) chunked document(s)."""

    doc_id: Optional[str] = Field(
        default=None,
        description="Target document ID.  Omit to embed all chunked documents.",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        le=256,
        description="Embedding batch size (higher = faster but more RAM).",
    )


class BatchEmbedRequest(BaseModel):
    """Request body for batch-embedding and indexing all documents at once."""

    batch_size: int = Field(
        default=32,
        ge=1,
        le=256,
        description="Embedding batch size.",
    )


# ---------------------------------------------------------------------------
# Search / answer request schemas
# ---------------------------------------------------------------------------

class SearchQueryRequest(QueryNormalizerMixin):
    """Request body for vector-store similarity search."""

    query: str = Field(..., min_length=1, description="Natural language search query.")
    top_k: int = Field(
        default=settings.RETRIEVAL_TOP_K,
        ge=1,
        le=50,
        description="Number of top-matching chunks to return.",
    )
    score_threshold: Optional[float] = Field(
        default=settings.RETRIEVAL_SCORE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score (0–1).  None disables filtering.",
    )
    reframe: bool = Field(
        default=False,
        description="Reframe the query with the LLM before retrieval for better recall.",
    )
    temperature: float = Field(
        default=settings.LLM_TEMPERATURE,
        ge=0.0,
        le=1.0,
        description="LLM sampling temperature for query reframing.",
    )


class AnswerQueryRequest(QueryNormalizerMixin):
    """Request body for grounded RAG answer generation."""

    query: str = Field(..., min_length=1, description="Natural language question.")
    top_k: int = Field(
        default=settings.RETRIEVAL_TOP_K,
        ge=1,
        le=50,
        description="Number of top context chunks to retrieve.",
    )
    score_threshold: Optional[float] = Field(
        default=settings.RETRIEVAL_SCORE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for context chunks.",
    )
    reframe: bool = Field(
        default=True,
        description="Reframe the query with the LLM before retrieval.",
    )
    temperature: float = Field(
        default=settings.LLM_TEMPERATURE,
        ge=0.0,
        le=1.0,
        description="LLM sampling temperature for answer generation.",
    )
    max_new_tokens: int = Field(
        default=settings.LLM_MAX_NEW_TOKENS,
        ge=64,
        le=2048,
        description="Maximum tokens to generate in the answer.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SearchResultItem(BaseModel):
    """A single chunk returned by vector-store search."""

    chunk_id: str
    doc_id: str
    url: str
    title: str
    text: str
    score: float
    chunk_index: int


class RAGEvaluationMetrics(BaseModel):
    """Production-grade RAG accuracy and performance evaluation metrics."""

    retrieval_confidence: float = Field(
        description="Average cosine similarity score of retrieved chunks (0.0 - 1.0)."
    )
    context_coverage: float = Field(
        description="Query term overlap ratio with retrieved context chunks (0.0 - 1.0)."
    )
    faithfulness_score: float = Field(
        description="Lexical groundedness score measuring answer support from context (0.0 - 1.0)."
    )
    retrieval_time_ms: float = Field(
        description="Time taken for vector similarity search and retrieval in milliseconds."
    )
    generation_time_ms: float = Field(
        description="Time taken for LLM answer generation in milliseconds."
    )
    total_time_ms: float = Field(
        description="Total RAG pipeline execution time in milliseconds."
    )


# Sentinel phrase used by generate_answer() when no relevant context is found.
# Keeping this constant here avoids circular imports and keeps service.py DRY.
NO_CONTEXT_SENTINEL = "I don't have information about that in the available data."


class AnswerResponse(BaseModel):
    """Grounded LLM answer with retrieved source chunks and production accuracy metrics."""

    query: str
    answer: str
    sources: List[SearchResultItem]
    evaluation: RAGEvaluationMetrics

    @computed_field  # type: ignore[misc]
    @property
    def sources_count(self) -> int:
        """Number of source chunks used to generate the answer."""
        return len(self.sources)

    @computed_field  # type: ignore[misc]
    @property
    def is_out_of_context(self) -> bool:
        """True when the query fell outside the indexed knowledge base.

        When True, ``sources`` will be empty and the ``answer`` will contain
        the standard no-information message.  Frontend clients can use this
        flag to show a distinct UI state instead of parsing the answer string.
        """
        return NO_CONTEXT_SENTINEL.lower() in self.answer.lower()


class PipelineStatusResponse(BaseModel):
    """Pipeline health and data-volume metrics."""

    scraped_document_count: int = Field(description="Number of raw scraped JSON files.")
    cleaned_document_count: int = Field(description="Number of cleaned JSON files.")
    chunked_document_count: int = Field(description="Number of chunked JSON files.")
    vector_count: int = Field(description="Total vectors in the store.")
    embedding_dimension: int = Field(description="Embedding model output dimension.")
    embedding_model: str = Field(description="Name of the active embedding model.")
    embedding_model_cached_locally: bool = Field(description="Whether the embedding model is cached.")
    llm_model: str = Field(description="Name of the active LLM.")
    llm_model_cached_locally: bool = Field(description="Whether the LLM is cached locally.")
    vector_store_stats: Dict[str, Any] = Field(description="Detailed vector store diagnostics.")
