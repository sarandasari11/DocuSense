from pathlib import Path
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "DocuSense"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"
    
    # Storage & DB
    DATABASE_URL: str = "sqlite:///./docusense.db"
    STORAGE_DIR: str = "./storage/documents"
    
    # Vector DB (Qdrant)
    QDRANT_HOST: Optional[str] = "localhost"
    QDRANT_PORT: Optional[int] = 6333
    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_PATH: Optional[str] = "./storage/qdrant"  # Used when running local file-based Qdrant
    QDRANT_USE_LOCAL_STORAGE: bool = True  # True allows running without Docker
    QDRANT_COLLECTION: str = "docusense_chunks"
    
    # Embeddings & Re-ranking
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = "gemini"  # "gemini" | "openai" | "ollama" | "mock"
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL_NAME: str = "gemini-1.5-flash"
    
    # RAG Hyperparameters
    RETRIEVAL_TOP_K_DENSE: int = 20
    RETRIEVAL_TOP_K_SPARSE: int = 20
    RERANK_TOP_K: int = 5
    RRF_K: int = 60

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )

    @model_validator(mode="after")
    def validate_environment(self):
        if self.APP_ENV not in {"development", "production", "test"}:
            raise ValueError("APP_ENV must be development, test, or production")

        if self.APP_ENV == "production":
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("Production requires DATABASE_URL to point to PostgreSQL")
            if self.QDRANT_USE_LOCAL_STORAGE:
                raise ValueError("Production requires QDRANT_USE_LOCAL_STORAGE=false")
            if not self.QDRANT_URL:
                raise ValueError("Production requires QDRANT_URL")
            self.DEBUG = False

        if self.APP_ENV != "production" and self.APP_ENV != "test":
            self.DEBUG = True
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
