import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    GEMINI_API: Optional[str] = None
    CEREBRAS_API_KEY_3: str

    # Paths
    # If paths are relative, they will be resolved relative to the Backend directory
    INDEX_DIR: str = "RAG/Embedding/faq_vector_index"
    MEMORY_DIR: str = "memory_sessions"
    
    # Models
    EMBED_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    @property
    def resolved_index_dir(self) -> str:
        if os.path.isabs(self.INDEX_DIR):
            return self.INDEX_DIR
        return os.path.join(os.path.dirname(__file__), self.INDEX_DIR)

    @property
    def resolved_memory_dir(self) -> str:
        if os.path.isabs(self.MEMORY_DIR):
            return self.MEMORY_DIR
        return os.path.join(os.path.dirname(__file__), self.MEMORY_DIR)
    
    # Retrieval Settings
    FAISS_K: int = 12
    BM25_K: int = 12
    RERANK_TOP_N: int = 5
    MAX_CONTEXT_CHARS: int = 12000
    MEMORY_TURNS: int = 6
    RETRIEVAL_CONFIDENCE_THRESHOLD: float = 0.1
    QUERY_REWRITE_HISTORY_TURNS: int = 3
    
    # Security & Limits
    RATE_LIMIT_RPS: float = 3.0
    BACKEND_SECRET_KEY: str = "playage-bo-secret-2024"
    
    # URLs
    USERGUIDE_BASE_URL: str = "https://userguide.playagegaming.tech/en/bo/"
    FAVICON_URL: str = "https://userguide.playagegaming.tech/favicon.ico"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()
