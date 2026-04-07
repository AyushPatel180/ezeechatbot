"""Pydantic settings for EzeeChatBot."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # API Keys
    OPENAI_API_KEY: str
    
    # LLM Model Configuration
    LLM_MODEL: str = "gpt-4.1-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Infrastructure
    QDRANT_URL: str = "http://localhost:6333"
    SQLITE_DB_PATH: str = "./stats.db"
    LITELLM_PROXY_URL: str = "http://litellm-proxy:4000"
    
    # Langfuse Observability
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://localhost:3000"
    
    # Processing Limits
    MAX_UPLOAD_CHARS: int = 500000
    MAX_CHUNK_TOKENS: int = 400
    OVERLAP_TOKENS: int = 50
    N_RETRIEVAL_RESULTS: int = 5
    PDF_OCR_ENABLED: bool = True
    PDF_OCR_MIN_IMAGE_COUNT: int = 1
    PDF_OCR_RENDER_DPI: int = 110
    PDF_OCR_MAX_PAGES: int = 5
    PDF_OCR_MIN_TEXT_CHARS: int = 40
    PDF_VISION_ENABLED: bool = False
    PDF_VISION_MODEL: str = "gpt-4.1-mini"
    PDF_VISION_RENDER_DPI: int = 110
    PDF_VISION_MAX_PAGES: int = 3
    PDF_VISION_MIN_IMAGE_COUNT: int = 1
    PDF_VISION_MIN_TEXT_CHARS: int = 80
    PDF_VISION_TIMEOUT_SEC: int = 12
    
    # RAG Thresholds
    SIMILARITY_THRESHOLD: float = 0.30
    
    # Logging
    LOG_LEVEL: str = "INFO"


# Global settings instance
settings = Settings()
