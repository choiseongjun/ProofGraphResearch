"""Batch-oriented public evidence collection for scalable RAG ingestion."""
from __future__ import annotations

from app.document_loader import load_url
from app.rag_repository import RagRepository
from app.artifact_store import archive_source_document
from app.crawl_policy import canonical_url


def collect_topic(topic: str, max_sources: int) -> tuple[list[dict], int]:
    # Imported lazily to avoid the workflow module becoming an API dependency at startup.
    from app.research_graph import _search_one

    queries = [f"{topic} market analysis", f"{topic} statistics", f"{topic} regulations", f"{topic} case study"]
    discovered: list[dict] = []
    seen: set[str] = set()
    for query in queries:
        for source in _search_one(query):
            url = canonical_url(source.get("url")) if source.get("url") else None
            if url and url not in seen:
                seen.add(url); discovered.append(source)
                if len(discovered) >= max_sources: break
        if len(discovered) >= max_sources: break
    documents, failures = [], 0
    for source in discovered:
        try:
            documents.append(load_url(source["url"]))
        except Exception:
            if source.get("content"):
                documents.append(source)
            else:
                failures += 1
    return documents, failures


def ingest_topics(topics: list[str], max_sources: int, on_progress) -> dict[str, int]:
    repository = RagRepository()
    processed = chunks = failed = 0
    for topic in topics:
        documents, load_failures = collect_topic(topic, max_sources)
        failed += load_failures
        if documents:
            for document in documents:
                try:
                    document["artifact_uri"] = archive_source_document(document)
                except Exception:
                    # Object storage is an audit layer; indexing remains available during storage outages.
                    document["artifact_uri"] = None
            chunks += repository.ingest(documents, source="bulk_automatic_web_crawl")
            processed += len(documents)
        on_progress(processed, chunks, failed)
    return {"processed_documents": processed, "indexed_chunks": chunks, "failed_documents": failed}
