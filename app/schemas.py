from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


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
