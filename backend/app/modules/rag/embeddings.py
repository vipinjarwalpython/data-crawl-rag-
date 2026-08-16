"""
Embedding model manager for CrawlRAG.

Handles lazy loading of the sentence-transformer model with:
- Local cache in models/embeddings  (no repeated downloads)
- Retry logic for unreliable network downloads
- Embedding dimension validation to catch model-swap mismatches early
"""

import os
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import get_module_logger

logger = get_module_logger(__name__)


class EmbeddingManager:
    """Lazy-loading manager for the all-MiniLM-L6-v2 sentence-transformer model.

    The model is downloaded once into ``models/embeddings`` and loaded from
    disk on every subsequent application start.  Embedding vectors are always
    L2-normalised so that cosine similarity reduces to a dot product.
    """

    # Maximum number of download/load attempts before giving up.
    MAX_LOAD_ATTEMPTS: int = 3
    # Seconds to wait between retry attempts (doubles each time).
    RETRY_BASE_DELAY_SECONDS: float = 2.0

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name: str = model_name or settings.DEFAULT_EMBEDDING_MODEL
        self.embedding_dimension: int = settings.EMBEDDING_DIMENSION
        self.cache_dir: Path = settings.resolve_path(settings.EMBEDDINGS_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._model: Optional[SentenceTransformer] = None

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def get_model(self) -> SentenceTransformer:
        """Return the loaded sentence-transformer model.

        Downloads the model on first call; returns the cached instance on
        subsequent calls.  Retries up to ``MAX_LOAD_ATTEMPTS`` times with
        exponential back-off if the download fails.
        """
        if self._model is not None:
            return self._model

        os.environ["HF_HOME"] = str(self.cache_dir)

        last_error: Exception | None = None
        for attempt in range(1, self.MAX_LOAD_ATTEMPTS + 1):
            try:
                logger.info(
                    "Loading embedding model '%s' (attempt %d/%d, cache: %s) …",
                    self.model_name,
                    attempt,
                    self.MAX_LOAD_ATTEMPTS,
                    self.cache_dir,
                )
                model = SentenceTransformer(
                    self.model_name,
                    cache_folder=str(self.cache_dir),
                )

                # Validate the output dimension against our expected value.
                self._validate_embedding_dimension(model)

                self._model = model
                logger.info(
                    "Embedding model '%s' loaded successfully (dim=%d).",
                    self.model_name,
                    self.embedding_dimension,
                )
                return self._model

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "Embedding model load attempt %d/%d failed: %s",
                    attempt,
                    self.MAX_LOAD_ATTEMPTS,
                    exc,
                )
                if attempt < self.MAX_LOAD_ATTEMPTS:
                    sleep_seconds = self.RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.info("Retrying embedding model load in %.1fs …", sleep_seconds)
                    time.sleep(sleep_seconds)

        raise RuntimeError(
            f"Failed to load embedding model '{self.model_name}' after "
            f"{self.MAX_LOAD_ATTEMPTS} attempts. Last error: {last_error}"
        )

    def _validate_embedding_dimension(self, model: SentenceTransformer) -> None:
        """Raise ValueError if model output dimension differs from expected."""
        probe_text = "dimension validation probe"
        probe_embedding: np.ndarray = model.encode([probe_text])
        actual_dim = probe_embedding.shape[1]

        if actual_dim != self.embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: model '{self.model_name}' "
                f"produces {actual_dim}-dim vectors but "
                f"EMBEDDING_DIMENSION={self.embedding_dimension} is configured. "
                "Update EMBEDDING_DIMENSION in .env or re-index with the correct model."
            )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Encode *texts* into L2-normalised float32 embedding vectors.

        Parameters
        ----------
        texts:
            List of strings to embed.
        batch_size:
            Number of texts to encode per GPU/CPU batch.

        Returns
        -------
        np.ndarray of shape (len(texts), embedding_dimension)
        """
        if not texts:
            return np.empty((0, self.embedding_dimension), dtype=np.float32)

        model = self.get_model()
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,   # cosine sim = dot product on unit vectors
        )
        return np.array(embeddings, dtype=np.float32)

    def is_cached_locally(self) -> bool:
        """Return True if model files already exist in the local cache."""
        return self.cache_dir.exists() and any(self.cache_dir.iterdir())

    def get_model_info(self) -> dict:
        """Return a summary dict describing the current embedding model state."""
        return {
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "is_loaded": self._model is not None,
            "is_cached_locally": self.is_cached_locally(),
            "cache_dir": str(self.cache_dir),
        }


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere instead of instantiating.
# ---------------------------------------------------------------------------
embedding_manager = EmbeddingManager()
