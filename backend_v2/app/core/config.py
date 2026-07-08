from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path

# Repo root .env (same pattern as backend; one level deeper: app/core -> backend_v2)
_candidate = Path(__file__).resolve().parent.parent.parent.parent / ".env"
ENV_FILE = str(_candidate) if _candidate.exists() else ".env"


class Settings(BaseSettings):
    APP_NAME: str = "JobNexus (Recommendation)"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # backend_v2 folder (uploads/, data/)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5433/nexusrag")

    LLM_PROVIDER: str = Field(default="gemini")
    GOOGLE_AI_API_KEY: str = Field(default="")
    OLLAMA_HOST: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="gemma3:12b")
    OLLAMA_ENABLE_THINKING: bool = Field(default=False)
    LLM_MODEL_FAST: str = Field(default="gemini-2.5-flash")
    LLM_THINKING_LEVEL: str = Field(default="medium")
    LLM_MAX_OUTPUT_TOKENS: int = Field(default=8192)

    KG_EMBEDDING_PROVIDER: str = Field(default="gemini")
    KG_EMBEDDING_MODEL: str = Field(default="gemini-embedding-001")
    KG_EMBEDDING_DIMENSION: int = Field(default=3072)

    CHROMA_HOST: str = Field(default="localhost")
    CHROMA_PORT: int = Field(default=8002)

    NEXUSRAG_ENABLED: bool = True
    NEXUSRAG_ENABLE_KG: bool = False
    NEXUSRAG_ENABLE_IMAGE_EXTRACTION: bool = True
    NEXUSRAG_ENABLE_IMAGE_CAPTIONING: bool = True
    NEXUSRAG_ENABLE_TABLE_CAPTIONING: bool = True
    NEXUSRAG_MAX_TABLE_MARKDOWN_CHARS: int = 8000
    NEXUSRAG_CHUNK_MAX_TOKENS: int = 512
    NEXUSRAG_KG_QUERY_TIMEOUT: float = 30.0
    NEXUSRAG_KG_CHUNK_TOKEN_SIZE: int = 1200
    NEXUSRAG_KG_LANGUAGE: str = "Vietnamese"
    NEXUSRAG_KG_ENTITY_TYPES: list[str] = [
        "Skill", "JobTitle", "Company", "Industry", "Certification",
        "University", "Location", "Technology", "Person",
    ]
    NEXUSRAG_DEFAULT_QUERY_MODE: str = "hybrid"
    NEXUSRAG_DOCLING_IMAGES_SCALE: float = 2.0
    NEXUSRAG_MAX_IMAGES_PER_DOC: int = 50
    NEXUSRAG_ENABLE_FORMULA_ENRICHMENT: bool = True

    NEXUSRAG_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    NEXUSRAG_RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    NEXUSRAG_VECTOR_PREFETCH: int = 20
    NEXUSRAG_RERANKER_TOP_K: int = 8
    NEXUSRAG_MIN_RELEVANCE_SCORE: float = 0.15

    MATCHING_SEMANTIC_WEIGHT: float = 0.50
    MATCHING_SKILL_WEIGHT: float = 0.25
    MATCHING_EXPERIENCE_WEIGHT: float = 0.10
    MATCHING_LOCATION_WEIGHT: float = 0.10
    MATCHING_SALARY_WEIGHT: float = 0.05

    CORS_ORIGINS: list[str] = [
        "https://ai.itrecruitment.dpdns.org",
        "https://itrecruitment.dpdns.org",
        "http://localhost:5174",
        "http://localhost:3000",
    ]

    # API key auth for public API
    API_KEY_ENABLED: bool = Field(default=False)
    API_KEYS: str = Field(default="")
    API_KEY_HEADER: str = Field(default="X-API-Key")
    API_KEY_PROTECTED_PREFIXES: str = Field(default="/api/")
    API_KEY_EXCLUDED_PREFIXES: str = Field(
        default="/health,/ready,/docs,/redoc,/openapi.json,/static/"
    )

    model_config = {
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
