from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    llm_provider: str = "openai"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: int = 600
    tavily_api_key: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://research:research@localhost:5432/research"
    max_revisions: int = 2
    app_api_key: str | None = None
    report_retention_days: int = 30
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "research-graph-password"
    artifact_storage_enabled: bool = False
    artifact_bucket: str = "proofgraph-reports"
    raw_document_storage_enabled: bool = False
    raw_document_bucket: str = "proofgraph-raw"
    aws_endpoint_url: str | None = None
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    rag_top_k: int = 5
    embedding_batch_size: int = 32
    vector_backend: str = "pgvector"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "proofgraph_knowledge"
    ingestion_max_sources_per_topic: int = 8
    crawler_user_agent: str = "ProofGraphResearch/1.0 (+research indexing)"
    crawler_request_interval_seconds: float = 1.0
    crawler_respect_robots_txt: bool = True
    frontend_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
