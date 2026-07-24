"""PostgreSQL persistence for jobs, provenance, event timeline, and quality metrics."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.engine import Engine
from pgvector.sqlalchemy import Vector
from app.config import get_settings

metadata = MetaData()
jobs = Table(
    "research_jobs", metadata,
    Column("task_id", String(36), primary_key=True), Column("status", String(16), nullable=False),
    Column("topic", Text, nullable=False), Column("audience", Text, nullable=False), Column("depth", String(16), nullable=False),
    Column("report", Text), Column("error", Text), Column("metrics", JSON),
    Column("retry_of", String(36)), Column("attempt_count", Integer, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False), Column("updated_at", DateTime(timezone=True), nullable=False),
)
events = Table(
    "research_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("task_id", String(36), ForeignKey("research_jobs.task_id"), nullable=False),
    Column("phase", String(32), nullable=False), Column("message", Text, nullable=False), Column("details", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
sources = Table(
    "research_sources", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("task_id", String(36), ForeignKey("research_jobs.task_id"), nullable=False),
    Column("source_number", Integer, nullable=False), Column("title", Text, nullable=False), Column("url", Text), Column("content", Text),
    Column("source_type", String(16), nullable=False, default="web"), Column("created_at", DateTime(timezone=True), nullable=False),
)
knowledge_documents = Table(
    "knowledge_documents", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("title", Text, nullable=False), Column("url", Text), Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)
knowledge_chunks = Table(
    "knowledge_chunks", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("document_key", String(128), nullable=False, index=True),
    Column("title", Text, nullable=False), Column("url", Text), Column("content", Text, nullable=False),
    Column("metadata", JSON, nullable=False, default=dict), Column("embedding", Vector(768), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobStore:
    def __init__(self) -> None:
        self.engine: Engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        metadata.create_all(self.engine)
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                conn.exec_driver_sql("ALTER TABLE research_jobs ADD COLUMN IF NOT EXISTS retry_of VARCHAR(36)")
                conn.exec_driver_sql("ALTER TABLE research_jobs ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0")

    @staticmethod
    def _record(row: Any) -> dict[str, Any]:
        value = dict(row)
        for key in ("created_at", "updated_at"):
            if key in value and value[key]: value[key] = value[key].isoformat()
        return value

    def create(self, task_id: str, payload: dict[str, Any], retry_of: str | None = None) -> dict[str, Any]:
        stamp = _now()
        with self.engine.begin() as conn:
            conn.execute(jobs.insert().values(task_id=task_id, status="queued", topic=payload["topic"], audience=payload["audience"], depth=payload["depth"], retry_of=retry_of, attempt_count=0, created_at=stamp, updated_at=stamp))
        self.append_event(task_id, "queued", "리서치 작업이 대기열에 추가되었습니다.")
        return self.get(task_id)  # type: ignore[return-value]

    def update(self, task_id: str, **changes: Any) -> dict[str, Any]:
        changes["updated_at"] = _now()
        with self.engine.begin() as conn:
            conn.execute(jobs.update().where(jobs.c.task_id == task_id).values(**changes))
        return self.get(task_id)  # type: ignore[return-value]

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(jobs).where(jobs.c.task_id == task_id)).mappings().first()
        return self._record(row) if row else None

    def append_event(self, task_id: str, phase: str, message: str, details: dict[str, Any] | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(events.insert().values(task_id=task_id, phase=phase, message=message, details=details or {}, created_at=_now()))

    def list_events(self, task_id: str, after: int = 0) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(events).where(events.c.task_id == task_id, events.c.id > after).order_by(events.c.id)).mappings().all()
        return [self._record(row) | {"sequence": row["id"]} for row in rows]

    def save_sources(self, task_id: str, items: list[dict[str, str]]) -> None:
        values = [{"task_id": task_id, "source_number": index + 1, "title": item["title"], "url": item.get("url"), "content": item.get("content"), "source_type": "internal" if item["title"].startswith("[내부 DB]") else "web", "created_at": _now()} for index, item in enumerate(items)]
        if values:
            with self.engine.begin() as conn: conn.execute(sources.insert(), values)

    def list_sources(self, task_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(sources).where(sources.c.task_id == task_id).order_by(sources.c.source_number)).mappings().all()
        return [self._record(row) for row in rows]

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(jobs).order_by(jobs.c.created_at.desc()).limit(limit)).mappings().all()
        return [self._record(row) for row in rows]
