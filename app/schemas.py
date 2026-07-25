from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


JobStatus = Literal["queued", "running", "completed", "failed"]


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=500, examples=["2026년 한국 AI 에이전트 시장 동향"])
    audience: str = Field(default="신사업 임원", min_length=2, max_length=200)
    depth: Literal["brief", "standard", "deep"] = "standard"


class ResearchJob(BaseModel):
    task_id: str
    status: JobStatus
    created_at: datetime


class ResearchResult(BaseModel):
    task_id: str
    status: JobStatus
    topic: str | None = None
    audience: str | None = None
    depth: str | None = None
    report: str | None = None
    error: str | None = None
    metrics: dict[str, Any] | None = None
    retry_of: str | None = None
    attempt_count: int = 0
    updated_at: datetime


class AgentEvent(BaseModel):
    sequence: int
    phase: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EvaluationResult(BaseModel):
    task_id: str
    citation_score: int
    cited_references: int
    source_count: int
    invalid_citations: list[int]
    summary: str


class KnowledgeDocumentRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=200_000)
    url: str | None = None

    @model_validator(mode="after")
    def content_or_url_is_required(self):
        if not self.content and not self.url:
            raise ValueError("Provide content or a URL.")
        return self


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeCrawlRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=500)
    max_sources: int = Field(default=6, ge=1, le=12)


class BulkIngestionRequest(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=100)
    max_sources_per_topic: int = Field(default=8, ge=1, le=20)


class IngestionJob(BaseModel):
    job_id: str
    status: str
    topics: list[str]
    processed_documents: int
    indexed_chunks: int
    failed_documents: int
    error: str | None = None
    created_at: datetime
    updated_at: datetime
