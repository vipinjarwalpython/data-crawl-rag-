from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and environment settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # App Info
    APP_NAME: str = "CrawlRAG"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = Field(default_factory=lambda: Path("data"))
    SCRAPED_DIR: Path = Field(default_factory=lambda: Path("data/scraped"))
    PROCESSED_DIR: Path = Field(default_factory=lambda: Path("data/processed"))
    VECTOR_STORE_DIR: Path = Field(default_factory=lambda: Path("data/vector_store"))
    MODELS_DIR: Path = Field(default_factory=lambda: Path("models"))
    EMBEDDINGS_DIR: Path = Field(default_factory=lambda: Path("models/embeddings"))
    LLM_DIR: Path = Field(default_factory=lambda: Path("models/llm"))

    # Scraping Defaults
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

    # Model & RAG Defaults
    DEFAULT_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    DEFAULT_CHUNK_SIZE: int = 250
    DEFAULT_CHUNK_OVERLAP: int = 50
    DEFAULT_LLM_MODEL: str = "Qwen/Qwen2.5-0.5B-Instruct"

    def ensure_directories(self) -> None:
        """Ensure all required runtime data and model directories exist."""
        for path in [
            self.DATA_DIR,
            self.SCRAPED_DIR,
            self.PROCESSED_DIR,
            self.VECTOR_STORE_DIR,
            self.MODELS_DIR,
            self.EMBEDDINGS_DIR,
            self.LLM_DIR,
        ]:
            full_path = self.BASE_DIR / path if not path.is_absolute() else path
            full_path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
