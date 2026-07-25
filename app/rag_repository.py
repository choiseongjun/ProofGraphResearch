"""Persistent pgvector retrieval for evidence-first RAG."""
from __future__ import annotations

import hashlib
import logging
from uuid import NAMESPACE_URL, uuid5
from typing import Any

import httpx
from sqlalchemy import text

from app.config import get_settings
from app.store import JobStore, knowledge_chunks

logger = logging.getLogger(__name__)


def _chunks(content: str, size: int = 1000, overlap: int = 160) -> list[str]:
    # PostgreSQL TEXT rejects NUL; crawled files can contain malformed binary fragments.
    normalized = " ".join(content.replace("\x00", " ").split())
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
            if url:
                is_changed, version = self.store.register_crawl_document(url, hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest(), document.get("etag"), document.get("last_modified"))
                if not is_changed:
                    continue
            else:
                version = 1
            for index, chunk in enumerate(_chunks(content)):
                pending.append({"document_key": document_key, "title": title, "url": url, "content": chunk, "metadata": {"source": source, "chunk": index, "version": version, "artifact_uri": document.get("artifact_uri")}})
        if not pending:
            return 0
        inserted = 0
        batch_size = get_settings().embedding_batch_size
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            vectors = self.embed([item["content"] for item in batch])
            if len(vectors) != len(batch):
                raise RuntimeError("Embedding response count does not match chunk count.")
            with self.engine.begin() as conn:
                for item, vector in zip(batch, vectors):
                    exists = conn.execute(text("SELECT 1 FROM knowledge_chunks WHERE document_key = :key AND content = :content LIMIT 1"), {"key": item["document_key"], "content": item["content"]}).first()
                    if not exists:
                        conn.execute(knowledge_chunks.insert().values(**item, embedding=vector))
                        inserted += 1
            if get_settings().vector_backend == "qdrant":
                self._upsert_qdrant(batch, vectors)
        return inserted

    @staticmethod
    def _qdrant_client():
        from qdrant_client import QdrantClient
        settings = get_settings()
        return QdrantClient(url=settings.qdrant_url)

    def _ensure_qdrant_collection(self) -> None:
        from qdrant_client.http.models import Distance, VectorParams
        settings = get_settings()
        client = self._qdrant_client()
        if not client.collection_exists(settings.qdrant_collection):
            client.create_collection(settings.qdrant_collection, vectors_config=VectorParams(size=settings.embedding_dimensions, distance=Distance.COSINE))

    def _upsert_qdrant(self, batch: list[dict[str, Any]], vectors: list[list[float]]) -> None:
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue, PointStruct
        settings = get_settings()
        self._ensure_qdrant_collection()
        client = self._qdrant_client()
        # PostgreSQL keeps every version for audit; the serving index keeps the latest URL version only.
        for url in {item["url"] for item in batch if item["url"]}:
            client.delete(collection_name=settings.qdrant_collection, points_selector=Filter(must=[FieldCondition(key="url", match=MatchValue(value=url))]), wait=True)
        points = [PointStruct(id=str(uuid5(NAMESPACE_URL, f"{item['document_key']}:{item['metadata']['chunk']}")), vector=vector, payload={"title": item["title"], "url": item["url"], "content": item["content"], "metadata": item["metadata"]}) for item, vector in zip(batch, vectors)]
        client.upsert(collection_name=settings.qdrant_collection, points=points, wait=True)

    def search(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        vector = self.embed([query])[0]
        if get_settings().vector_backend == "qdrant":
            return self._search_qdrant(vector, limit or get_settings().rag_top_k)
        serialized = "[" + ",".join(str(value) for value in vector) + "]"
        count = limit or get_settings().rag_top_k
        statement = text("""
            SELECT title, url, content, metadata, 1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM knowledge_chunks ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(statement, {"embedding": serialized, "limit": count}).mappings().all()
        return [dict(row) for row in rows]

    def _search_qdrant(self, vector: list[float], limit: int) -> list[dict[str, Any]]:
        settings = get_settings()
        client = self._qdrant_client()
        if not client.collection_exists(settings.qdrant_collection):
            return []
        response = client.query_points(collection_name=settings.qdrant_collection, query=vector, limit=limit, with_payload=True)
        return [{"title": point.payload.get("title"), "url": point.payload.get("url"), "content": point.payload.get("content"), "metadata": point.payload.get("metadata", {}), "score": point.score} for point in response.points]

    def sync_postgres_to_qdrant(self) -> int:
        """One-time backfill for vectors created before VECTOR_BACKEND=qdrant."""
        from qdrant_client.http.models import PointStruct
        self._ensure_qdrant_collection()
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT document_key, title, url, content, metadata, embedding::text AS embedding FROM knowledge_chunks")).mappings().all()
        points = []
        for row in rows:
            metadata = row["metadata"] or {}
            chunk = metadata.get("chunk", 0)
            vector = [float(item) for item in row["embedding"].strip("[]").split(",")]
            points.append(PointStruct(id=str(uuid5(NAMESPACE_URL, f"{row['document_key']}:{chunk}")), vector=vector, payload={"title": row["title"], "url": row["url"], "content": row["content"], "metadata": metadata}))
        if points:
            self._qdrant_client().upsert(collection_name=get_settings().qdrant_collection, points=points, wait=True)
        return len(points)
