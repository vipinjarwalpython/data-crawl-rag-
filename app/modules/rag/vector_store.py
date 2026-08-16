"""
Persistent vector store for CrawlRAG.

Stores embedding vectors and associated chunk metadata on disk using numpy
(.npy) + JSON formats.  Provides cosine-similarity search (dot-product on
L2-normalised vectors), dimension validation, deduplication, and stats.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.config import settings
from app.core.logging import get_module_logger

logger = get_module_logger(__name__)


class VectorStore:
    """Disk-backed vector store with cosine-similarity search.

    Vectors must be L2-normalised before insertion (the EmbeddingManager
    guarantees this).  Cosine similarity then reduces to a plain dot product,
    which is fast with numpy.

    File layout on disk::

        data/vector_store/
            vector_index.npy     — float32 matrix of shape (N, dim)
            metadata.json        — list of N chunk dicts
    """

    INDEX_FILENAME = "vector_index.npy"
    METADATA_FILENAME = "metadata.json"

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self.store_dir: Path = store_dir or settings.resolve_path(settings.VECTOR_STORE_DIR)
        self.store_dir.mkdir(parents=True, exist_ok=True)

        self.index_file_path: Path = self.store_dir / self.INDEX_FILENAME
        self.metadata_file_path: Path = self.store_dir / self.METADATA_FILENAME

        self.expected_dimension: int = settings.EMBEDDING_DIMENSION

        # In-memory state
        self.vectors: np.ndarray = np.empty((0, self.expected_dimension), dtype=np.float32)
        self.chunk_metadata: List[Dict[str, Any]] = []

        self._load_from_disk()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        """Load vector index and metadata from disk if both files exist."""
        if not (self.index_file_path.exists() and self.metadata_file_path.exists()):
            logger.info("No existing vector store found at '%s'. Starting empty.", self.store_dir)
            return

        try:
            loaded_vectors: np.ndarray = np.load(self.index_file_path)
            with self.metadata_file_path.open("r", encoding="utf-8") as metadata_file:
                loaded_metadata: List[Dict[str, Any]] = json.load(metadata_file)

            # Validate dimension matches current model configuration.
            if loaded_vectors.ndim == 2 and loaded_vectors.shape[1] != self.expected_dimension:
                logger.error(
                    "Vector store dimension mismatch: disk has %d-dim vectors but "
                    "EMBEDDING_DIMENSION=%d. Clearing store to avoid incorrect results. "
                    "Re-run /api/v1/rag/embed-all to rebuild the index.",
                    loaded_vectors.shape[1],
                    self.expected_dimension,
                )
                return

            self.vectors = loaded_vectors
            self.chunk_metadata = loaded_metadata
            logger.info(
                "Loaded vector store: %d vectors (dim=%d) from '%s'.",
                len(self.chunk_metadata),
                self.expected_dimension,
                self.store_dir,
            )

        except Exception as exc:
            logger.error(
                "Failed to load vector store from '%s': %s. Starting with empty store.",
                self.store_dir,
                exc,
                exc_info=True,
            )
            self.vectors = np.empty((0, self.expected_dimension), dtype=np.float32)
            self.chunk_metadata = []

    def save_to_disk(self) -> None:
        """Persist the current in-memory vector index and metadata to disk."""
        try:
            np.save(self.index_file_path, self.vectors)
            with self.metadata_file_path.open("w", encoding="utf-8") as metadata_file:
                json.dump(self.chunk_metadata, metadata_file, indent=2, ensure_ascii=False)
            logger.debug(
                "Saved vector store: %d vectors to '%s'.",
                len(self.chunk_metadata),
                self.store_dir,
            )
        except Exception as exc:
            logger.error(
                "Failed to save vector store to '%s': %s",
                self.store_dir,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_embeddings(
        self,
        new_vectors: np.ndarray,
        new_chunk_metadata: List[Dict[str, Any]],
    ) -> None:
        """Append *new_vectors* and *new_chunk_metadata* to the store.

        Parameters
        ----------
        new_vectors:
            Float32 array of shape (N, embedding_dimension).
        new_chunk_metadata:
            List of N chunk metadata dicts (must have a ``chunk_id`` key).
        """
        if len(new_vectors) != len(new_chunk_metadata):
            raise ValueError(
                f"Vector count ({len(new_vectors)}) must match "
                f"metadata count ({len(new_chunk_metadata)})."
            )

        # Validate the incoming dimension.
        if new_vectors.ndim != 2 or new_vectors.shape[1] != self.expected_dimension:
            raise ValueError(
                f"Expected vectors of shape (N, {self.expected_dimension}) "
                f"but received shape {new_vectors.shape}."
            )

        # Deduplicate: skip any chunk whose chunk_id is already stored.
        existing_chunk_ids = {item.get("chunk_id") for item in self.chunk_metadata}
        unique_vectors, unique_metadata = [], []
        for vector, metadata_item in zip(new_vectors, new_chunk_metadata):
            if metadata_item.get("chunk_id") not in existing_chunk_ids:
                unique_vectors.append(vector)
                unique_metadata.append(metadata_item)
                existing_chunk_ids.add(metadata_item.get("chunk_id"))

        duplicate_count = len(new_vectors) - len(unique_vectors)
        if duplicate_count:
            logger.debug("Skipped %d duplicate chunk(s) during add_embeddings.", duplicate_count)

        if not unique_vectors:
            logger.info("No new unique vectors to add.")
            return

        unique_vectors_array = np.array(unique_vectors, dtype=np.float32)

        if self.vectors.size == 0:
            self.vectors = unique_vectors_array
        else:
            self.vectors = np.vstack([self.vectors, unique_vectors_array])

        self.chunk_metadata.extend(unique_metadata)
        self.save_to_disk()

        logger.info(
            "Added %d new vectors (skipped %d duplicates). "
            "Total store size: %d vectors.",
            len(unique_vectors),
            duplicate_count,
            len(self.chunk_metadata),
        )

    def clear(self) -> None:
        """Remove all vectors and metadata, and delete disk files."""
        self.vectors = np.empty((0, self.expected_dimension), dtype=np.float32)
        self.chunk_metadata = []

        for file_path in (self.index_file_path, self.metadata_file_path):
            if file_path.exists():
                file_path.unlink()

        logger.info("Vector store cleared.")

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def compute_cosine_similarities(self, query_vector: np.ndarray) -> np.ndarray:
        """Return cosine similarity scores between *query_vector* and all stored vectors.

        Because all vectors are L2-normalised, this is just a dot product.
        """
        if self.vectors.size == 0:
            return np.empty(0, dtype=np.float32)

        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        # Validate query dimension.
        if query_vector.shape[1] != self.expected_dimension:
            raise ValueError(
                f"Query vector has {query_vector.shape[1]} dimensions "
                f"but store expects {self.expected_dimension}."
            )

        return np.dot(self.vectors, query_vector.T).squeeze(1)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve the top-*k* most similar chunks to *query_vector*.

        Parameters
        ----------
        query_vector:
            L2-normalised query embedding.
        top_k:
            Maximum number of results to return.
        score_threshold:
            When provided, results with a score below this value are dropped.
            If all results fall below the threshold the top result is still
            returned as a graceful fallback.
        """
        if self.vectors.size == 0 or not self.chunk_metadata:
            return []

        similarity_scores = self.compute_cosine_similarities(query_vector)
        if similarity_scores.size == 0:
            return []

        # Sort indices by descending score.
        sorted_indices = np.argsort(similarity_scores)[::-1]

        results: List[Dict[str, Any]] = []
        for index in sorted_indices[:top_k]:
            score = float(similarity_scores[index])
            if score_threshold is not None and score < score_threshold:
                continue
            chunk_item = dict(self.chunk_metadata[index])
            chunk_item["score"] = score
            results.append(chunk_item)

        return results

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the total number of stored vectors."""
        return len(self.chunk_metadata)

    def get_stats(self) -> Dict[str, Any]:
        """Return a diagnostic summary of the current vector store state."""
        disk_size_bytes = 0
        if self.index_file_path.exists():
            disk_size_bytes += self.index_file_path.stat().st_size
        if self.metadata_file_path.exists():
            disk_size_bytes += self.metadata_file_path.stat().st_size

        return {
            "vector_count": self.count(),
            "embedding_dimension": self.expected_dimension,
            "disk_size_bytes": disk_size_bytes,
            "store_dir": str(self.store_dir),
            "index_file_exists": self.index_file_path.exists(),
            "metadata_file_exists": self.metadata_file_path.exists(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
vector_store = VectorStore()
