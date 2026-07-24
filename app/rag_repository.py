"""Persistent pgvector retrieval for evidence-first RAG."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx
from sqlalchemy import text

from app.config import get_settings
from app.store import JobStore, knowledge_chunks

logger = logging.getLogger(__name__)


def _chunks(content: str, size: int = 1000, overlap: int = 160) -> list[str]:
    normalized = " ".join(content.split())
    if not normalized:
        return []
    return [normalized[start:start + size] for start in range(0, len(normalized), size - overlap)]


class RagRepository:
    def __init__(self) -> None:
        self.store = JobStore()
        self.engine = self.store.engine

    @staticmethod
    def _key(title: str, url: str | None, content: str) -> str:
        return hashlib.sha256(f"{title}|{url or ''}|{content}".encode()).hexdigest()

    def embed(self, texts: list[str]) -> list[list[float]]:
        settings = get_settings()
        if settings.embedding_provider != "ollama":
            raise ValueError("Only the local Ollama embedding provider is configured.")
        base = settings.ollama_base_url.rstrip("/")
        try:
            response = httpx.post(f"{base}/api/embed", json={"model": settings.embedding_model, "input": texts}, timeout=90)
            response.raise_for_status()
            embeddings = response.json().get("embeddings")
            if embeddings:
                return embeddings
        except httpx.HTTPError:
            pass
        vectors: list[list[float]] = []
        for value in texts:
            response = httpx.post(f"{base}/api/embeddings", json={"model": settings.embedding_model, "prompt": value}, timeout=90)
            response.raise_for_status()
            vectors.append(response.json()["embedding"])
        return vectors

    def ingest(self, documents: list[dict[str, Any]], source: str = "research") -> int:
        pending: list[dict[str, Any]] = []
        for document in documents:
            title, url, content = document.get("title", "Untitled"), document.get("url"), document.get("content", "")
            document_key = self._key(title, url, content)
            for index, chunk in enumerate(_chunks(content)):
                pending.append({"document_key": document_key, "title": title, "url": url, "content": chunk, "metadata": {"source": source, "chunk": index}})
        if not pending:
            return 0
        vectors = self.embed([item["content"] for item in pending])
        if len(vectors) != len(pending):
            raise RuntimeError("Embedding response count does not match chunk count.")
        with self.engine.begin() as conn:
            for item, vector in zip(pending, vectors):
                exists = conn.execute(text("SELECT 1 FROM knowledge_chunks WHERE document_key = :key AND content = :content LIMIT 1"), {"key": item["document_key"], "content": item["content"]}).first()
                if not exists:
                    conn.execute(knowledge_chunks.insert().values(**item, embedding=vector))
        return len(pending)

    def search(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        vector = self.embed([query])[0]
        serialized = "[" + ",".join(str(value) for value in vector) + "]"
        count = limit or get_settings().rag_top_k
        statement = text("""
            SELECT title, url, content, metadata, 1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM knowledge_chunks ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(statement, {"embedding": serialized, "limit": count}).mappings().all()
        return [dict(row) for row in rows]
