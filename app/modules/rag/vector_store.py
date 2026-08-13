import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import aiofiles
from app.core.config import settings
from app.core.logging import logger


class VectorStore:
    """High-performance vector store with numpy cosine similarity search

    and persistent metadata / index storage on disk.
    """

    def __init__(self, store_dir: Optional[Path] = None):
        self.store_dir = store_dir or (
            settings.BASE_DIR / settings.VECTOR_STORE_DIR
            if not settings.VECTOR_STORE_DIR.is_absolute()
            else settings.VECTOR_STORE_DIR
        )
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_dir / "vector_index.npy"
        self.metadata_path = self.store_dir / "metadata.json"

        self.vectors: np.ndarray = np.empty((0, 384), dtype=np.float32)  # all-MiniLM-L6-v2 dim is 384
        self.metadata: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Load vector index and metadata from disk if available."""
        try:
            if self.index_path.exists() and self.metadata_path.exists():
                self.vectors = np.load(self.index_path)
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                logger.info(f"Loaded vector store with {len(self.metadata)} vectors from {self.store_dir}")
        except Exception as e:
            logger.error(f"Failed to load vector store from disk: {e}")
            self.vectors = np.empty((0, 384), dtype=np.float32)
            self.metadata = []

    def save(self) -> None:
        """Persist vector index and metadata to disk."""
        try:
            np.save(self.index_path, self.vectors)
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved vector store ({len(self.metadata)} vectors) to {self.store_dir}")
        except Exception as e:
            logger.error(f"Failed to save vector store to disk: {e}")

    def add_embeddings(self, new_vectors: np.ndarray, new_metadata: List[Dict[str, Any]]) -> None:
        """Add new vectors and corresponding metadata chunks to the store."""
        if len(new_vectors) != len(new_metadata):
            raise ValueError("Number of vectors must match number of metadata items.")

        if self.vectors.size == 0:
            self.vectors = new_vectors
        else:
            self.vectors = np.vstack([self.vectors, new_vectors])

        self.metadata.extend(new_metadata)
        self.save()
        logger.info(f"Added {len(new_vectors)} vectors. Total store size: {len(self.metadata)}")

    def search(self, query_vector: np.ndarray, top_k: int = 5, score_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """Perform cosine similarity search against stored chunk vectors."""
        if self.vectors.size == 0 or not self.metadata:
            return []

        # Ensure query vector is 2D and normalized
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        # Cosine similarity for normalized vectors is simply dot product
        similarities = np.dot(self.vectors, query_vector.T).squeeze(1)

        # Sort descending by score
        sorted_indices = np.argsort(similarities)[::-1]

        results = []
        for idx in sorted_indices[:top_k]:
            score = float(similarities[idx])
            if score_threshold is not None and score < score_threshold:
                continue
            
            item = dict(self.metadata[idx])
            item["score"] = score
            results.append(item)

        return results

    def count(self) -> int:
        """Return total number of stored vectors."""
        return len(self.metadata)

    def clear(self) -> None:
        """Clear all vectors and metadata."""
        self.vectors = np.empty((0, 384), dtype=np.float32)
        self.metadata = []
        if self.index_path.exists():
            self.index_path.unlink()
        if self.metadata_path.exists():
            self.metadata_path.unlink()
        logger.info("Cleared vector store.")


vector_store = VectorStore()
