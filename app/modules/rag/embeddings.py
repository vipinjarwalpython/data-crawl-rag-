import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.core.logging import logger


class EmbeddingManager:
    """Manager for loading and running the free all-MiniLM-L6-v2 embedding model

    with local caching inside models/embeddings.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        self.cache_dir = settings.BASE_DIR / settings.EMBEDDINGS_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._model: Optional[SentenceTransformer] = None

    def get_model(self) -> SentenceTransformer:
        """Lazy load model, downloading from Hugging Face if not present locally."""
        if self._model is None:
            logger.info(f"Loading embedding model '{self.model_name}' (cache_dir: {self.cache_dir})...")
            # Set environment variable for huggingface cache
            os.environ["HF_HOME"] = str(self.cache_dir)
            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=str(self.cache_dir)
            )
            logger.info(f"Embedding model '{self.model_name}' loaded successfully.")
        return self._model

    def is_cached_locally(self) -> bool:
        """Check if model files exist in local models/embeddings directory."""
        # Check if any snapshot or model files exist
        if not self.cache_dir.exists():
            return False
        files = list(self.cache_dir.glob("**/*"))
        return len(files) > 0

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Encode a list of texts into normalized embedding vectors."""
        model = self.get_model()
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        return np.array(embeddings, dtype=np.float32)


embedding_manager = EmbeddingManager()
