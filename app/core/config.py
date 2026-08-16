"""
CrawlRAG application configuration.

All tuneable parameters are defined here and loaded from the .env file.
Centralising RAG, LLM, and scraping defaults here means a single place to
change behaviour without touching business logic.
"""

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application identity
    # ------------------------------------------------------------------
    APP_NAME: str = "CrawlRAG"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _coerce_debug_flag(cls, raw_value: Any) -> bool:
        """Accept both booleans and the common truthy/falsy string values."""
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, str):
            return raw_value.lower() in {"true", "1", "t", "yes", "y", "on"}
        return bool(raw_value)

    # ------------------------------------------------------------------
    # File-system paths  (relative paths are resolved against BASE_DIR)
    # ------------------------------------------------------------------
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    DATA_DIR: Path = Field(default_factory=lambda: Path("data"))
    SCRAPED_DIR: Path = Field(default_factory=lambda: Path("data/scraped"))
    CLEAN_DATA_DIR: Path = Field(default_factory=lambda: Path("data/clean_data"))
    CHUNKED_DATA_DIR: Path = Field(default_factory=lambda: Path("data/chunked_data"))
    VECTOR_STORE_DIR: Path = Field(default_factory=lambda: Path("data/vector_store"))

    MODELS_DIR: Path = Field(default_factory=lambda: Path("models"))
    EMBEDDINGS_DIR: Path = Field(default_factory=lambda: Path("models/embeddings"))
    LLM_DIR: Path = Field(default_factory=lambda: Path("models/llm"))

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_DIR: Path = Field(default_factory=lambda: Path("logs"))
    LOG_MAX_BYTES: int = 10 * 1024 * 1024   # 10 MB per rotating file
    LOG_BACKUP_COUNT: int = 5               # keep 5 rotated backups

    # ------------------------------------------------------------------
    # Web scraping defaults
    # ------------------------------------------------------------------
    DEFAULT_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36 CrawlRAG/1.0"
    )
    REQUEST_TIMEOUT_SECONDS: float = 30.0
    MAX_CONCURRENT_REQUESTS: int = 5
    REQUEST_DELAY_SECONDS: float = 0.5
    DEFAULT_MAX_DEPTH: int = 2
    DEFAULT_MAX_PAGES: int = 50

    # ------------------------------------------------------------------
    # Embedding model
    # ------------------------------------------------------------------
    DEFAULT_EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384          # bge-small-en-v1.5 output dim

    # ------------------------------------------------------------------
    # Chunking defaults  (tuned for retrieval accuracy)
    # ------------------------------------------------------------------
    DEFAULT_CHUNK_SIZE: int = 400           # smaller chunks → more precise retrieval
    DEFAULT_CHUNK_OVERLAP: int = 80         # wider overlap → fewer orphan sentences

    # ------------------------------------------------------------------
    # LLM / generation defaults
    # ------------------------------------------------------------------
    DEFAULT_LLM_MODEL: str = "Qwen/Qwen2.5-1.5B-Instruct"
    LLM_MAX_NEW_TOKENS: int = 512           # enough for complete answers
    LLM_TEMPERATURE: float = 0.1            # low = factual; 0.0 = fully deterministic

    # ------------------------------------------------------------------
    # RAG retrieval defaults
    # ------------------------------------------------------------------
    RETRIEVAL_TOP_K: int = 7                # more candidates → richer context
    RETRIEVAL_SCORE_THRESHOLD: float = 0.2  # lower floor → fewer empty results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolve_path(self, relative_path: Path) -> Path:
        """Return an absolute path by prepending BASE_DIR when needed."""
        return self.BASE_DIR / relative_path if not relative_path.is_absolute() else relative_path

    def ensure_directories(self) -> None:
        """Create all required runtime directories if they do not exist."""
        directories_to_create = [
            self.DATA_DIR,
            self.SCRAPED_DIR,
            self.CLEAN_DATA_DIR,
            self.CHUNKED_DATA_DIR,
            self.VECTOR_STORE_DIR,
            self.MODELS_DIR,
            self.EMBEDDINGS_DIR,
            self.LLM_DIR,
            self.LOG_DIR,
        ]
        for directory in directories_to_create:
            resolved = self.resolve_path(directory)
            resolved.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Global singleton — import this everywhere.
# ---------------------------------------------------------------------------
settings = Settings()
settings.ensure_directories()
