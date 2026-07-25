"""Prometheus metrics for the API, asynchronous work, and knowledge pipeline."""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily, REGISTRY

from app.config import get_settings

HTTP_REQUESTS = Counter("proofgraph_http_requests_total", "HTTP requests handled by the API", ["method", "path", "status"])
HTTP_DURATION = Histogram("proofgraph_http_request_duration_seconds", "HTTP request duration", ["method", "path"])
RESEARCH_REQUESTS = Counter("proofgraph_research_requests_total", "Research jobs accepted by the API")
INGESTION_REQUESTS = Counter("proofgraph_ingestion_requests_total", "Bulk ingestion jobs accepted by the API")


class ProofGraphCollector:
    """Build scrape-time gauges from PostgreSQL and Redis, the durable system state."""

    def collect(self):
        from app.store import JobStore

        store = JobStore()
        research = GaugeMetricFamily("proofgraph_research_jobs", "Research jobs by current state", labels=["status"])
        counts: dict[str, int] = {}
        for job in store.list_jobs(100):
            counts[job["status"]] = counts.get(job["status"], 0) + 1
        for status in ("queued", "running", "completed", "failed"):
            research.add_metric([status], counts.get(status, 0))
        yield research

        ingestion = GaugeMetricFamily("proofgraph_ingestion_jobs", "Bulk ingestion jobs by current state", labels=["status"])
        ingestion_counts: dict[str, int] = {}
        for job in store.list_ingestion_jobs(100):
            ingestion_counts[job["status"]] = ingestion_counts.get(job["status"], 0) + 1
        for status in ("queued", "running", "completed", "failed"):
            ingestion.add_metric([status], ingestion_counts.get(status, 0))
        yield ingestion

        chunks = GaugeMetricFamily("proofgraph_knowledge_chunks", "Persisted RAG chunks")
        chunks.add_metric([], store.count_knowledge_chunks())
        yield chunks

        queue = GaugeMetricFamily("proofgraph_celery_queue_messages", "Celery messages waiting by queue", labels=["queue"])
        try:
            import redis
            client = redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
            for name in ("celery", "ingestion"):
                queue.add_metric([name], client.llen(name))
        except Exception:
            pass
        yield queue


REGISTRY.register(ProofGraphCollector())


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
