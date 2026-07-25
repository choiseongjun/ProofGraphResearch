import asyncio
import json
import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.exporter import report_as_pdf
from app.quality import evaluate_citations
from app.schemas import AgentEvent, BulkIngestionRequest, EvaluationResult, IngestionJob, KnowledgeCrawlRequest, KnowledgeDocumentRequest, KnowledgeSearchRequest, ResearchJob, ResearchRequest, ResearchResult
from app.rag_repository import RagRepository
from app.document_loader import load_url
from app.workflow_registry import RESEARCH_WORKFLOW, list_workflows
from app.store import JobStore
from app.graph_repository import ResearchGraphRepository
from app.tasks import run_bulk_ingestion, run_research
from app.observability import HTTP_DURATION, HTTP_REQUESTS, INGESTION_REQUESTS, RESEARCH_REQUESTS, metrics_response

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("deep_research")
app = FastAPI(title="Evidence-first Deep Research", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().frontend_origins.split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="web"), name="static")


def authorize(x_api_key: str | None = Header(default=None), api_key: str | None = Query(default=None)) -> None:
    configured = get_settings().app_api_key
    if configured and x_api_key != configured and api_key != configured:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    path = request.url.path if request.url.path != "/metrics" else "/metrics"
    HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    HTTP_DURATION.labels(request.method, path).observe(time.perf_counter() - started)
    logger.info(json.dumps({"request_id": request_id, "method": request.method, "path": request.url.path, "status": response.status_code}))
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    with open("web/index.html", encoding="utf-8") as file:
        return file.read()


@app.get("/v1/workflows", dependencies=[Depends(authorize)])
def workflows() -> list[dict]:
    return list_workflows()


@app.get("/v1/workflows/{workflow_id}", dependencies=[Depends(authorize)])
def workflow_definition(workflow_id: str) -> dict:
    if workflow_id != RESEARCH_WORKFLOW.id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return RESEARCH_WORKFLOW.as_dict()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "evidence-first-deep-research"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    payload, content_type = metrics_response()
    return Response(content=payload, media_type=content_type)


@app.post("/v1/research", response_model=ResearchJob, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(authorize)])
@app.post("/research", response_model=ResearchJob, status_code=status.HTTP_202_ACCEPTED, include_in_schema=False, dependencies=[Depends(authorize)])
def create_research(request: ResearchRequest) -> ResearchJob:
    task_id = str(uuid4())
    record = JobStore().create(task_id, request.model_dump())
    run_research.delay(task_id, request.model_dump())
    RESEARCH_REQUESTS.inc()
    return ResearchJob(**record)


@app.get("/v1/research/{task_id}", response_model=ResearchResult, dependencies=[Depends(authorize)])
@app.get("/research/{task_id}", response_model=ResearchResult, include_in_schema=False, dependencies=[Depends(authorize)])
def get_research(task_id: str) -> ResearchResult:
    record = JobStore().get(task_id)
    if not record: raise HTTPException(status_code=404, detail="Research task not found")
    return ResearchResult(**record)


@app.post("/v1/research/{task_id}/retry", response_model=ResearchJob, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(authorize)])
def retry_research(task_id: str) -> ResearchJob:
    previous = JobStore().get(task_id)
    if not previous: raise HTTPException(status_code=404, detail="Research task not found")
    if previous["status"] not in {"failed", "completed"}: raise HTTPException(status_code=409, detail="Only finished jobs can be retried")
    retry_id = str(uuid4())
    payload = {"topic": previous["topic"], "audience": previous["audience"], "depth": previous["depth"]}
    record = JobStore().create(retry_id, payload, retry_of=task_id)
    run_research.delay(retry_id, payload)
    return ResearchJob(**record)


@app.get("/v1/research", response_model=list[ResearchResult], dependencies=[Depends(authorize)])
def list_research(limit: int = 20) -> list[ResearchResult]:
    return [ResearchResult(**record) for record in JobStore().list_jobs(min(max(limit, 1), 100))]


@app.get("/v1/metrics/summary", dependencies=[Depends(authorize)])
def metrics_summary() -> dict:
    completed = [item for item in JobStore().list_jobs(100) if item["status"] == "completed" and item.get("metrics") and item["metrics"].get("duration_ms")]
    if not completed: return {"completed_jobs": 0, "average_duration_ms": None, "average_citation_score": None, "providers": {}}
    durations = [item["metrics"].get("duration_ms", 0) for item in completed]
    scores = [item["metrics"].get("citation_score", 0) for item in completed]
    providers: dict[str, int] = {}
    for item in completed:
        key = f"{item['metrics'].get('provider', 'unknown')}:{item['metrics'].get('model', 'unknown')}"
        providers[key] = providers.get(key, 0) + 1
    return {"completed_jobs": len(completed), "average_duration_ms": round(sum(durations) / len(durations)), "average_citation_score": round(sum(scores) / len(scores), 1), "providers": providers}


@app.post("/v1/knowledge/documents", dependencies=[Depends(authorize)])
def ingest_knowledge(document: KnowledgeDocumentRequest) -> dict:
    try:
        item = document.model_dump()
        if item.get("url") and not item.get("content"):
            item = load_url(item["url"])
        item["title"] = item.get("title") or item.get("url") or "Manual knowledge"
        chunks = RagRepository().ingest([item], source="manual_upload")
        return {"indexed_chunks": chunks}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"RAG indexing unavailable: {exc}")


@app.post("/v1/knowledge/search", dependencies=[Depends(authorize)])
def search_knowledge(request: KnowledgeSearchRequest) -> dict:
    try:
        return {"results": RagRepository().search(request.query, request.limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"RAG retrieval unavailable: {exc}")


@app.post("/v1/knowledge/crawl", dependencies=[Depends(authorize)])
def crawl_knowledge(request: KnowledgeCrawlRequest) -> dict:
    """Discover public sources from a topic, fetch their full text, and index them."""
    from app.research_graph import _search_one
    from app.crawl_policy import canonical_url
    queries = [f"{request.topic} market analysis", f"{request.topic} statistics", f"{request.topic} regulations"]
    discovered: list[dict] = []
    seen: set[str] = set()
    for query in queries:
        for source in _search_one(query):
            url = canonical_url(source.get("url")) if source.get("url") else None
            if url and url not in seen:
                seen.add(url)
                discovered.append(source)
                if len(discovered) >= request.max_sources:
                    break
        if len(discovered) >= request.max_sources:
            break
    loaded, failed = [], []
    for source in discovered:
        try:
            loaded.append(load_url(source["url"]))
        except Exception:
            # Search snippets are still attributable evidence if a source blocks crawling.
            if source.get("content"):
                loaded.append(source)
            else:
                failed.append(source["url"])
    try:
        # Keep the single-topic UI flow subject to the same evidence-retention
        # policy as the asynchronous bulk ingestion flow.
        from app.artifact_store import archive_source_document
        for document in loaded:
            try:
                document["artifact_uri"] = archive_source_document(document)
            except Exception:
                document["artifact_uri"] = None
        chunks = RagRepository().ingest(loaded, source="automatic_web_crawl")
        return {"discovered_sources": len(discovered), "indexed_documents": len(loaded), "indexed_chunks": chunks, "failed_urls": failed}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Automatic RAG collection unavailable: {exc}")


@app.post("/v1/knowledge/vector-sync", dependencies=[Depends(authorize)])
def sync_vectors_to_qdrant() -> dict:
    """Backfill the dedicated vector store from PostgreSQL without re-crawling sources."""
    try:
        return {"synced_chunks": RagRepository().sync_postgres_to_qdrant()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Qdrant synchronization unavailable: {exc}")


@app.post("/v1/ingestion/jobs", response_model=IngestionJob, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(authorize)])
def create_bulk_ingestion(request: BulkIngestionRequest) -> IngestionJob:
    """Queue a large topic batch; a dedicated worker applies backpressure through bounded embedding batches."""
    job_id = str(uuid4())
    store = JobStore()
    record = store.create_ingestion_job(job_id, request.topics)
    run_bulk_ingestion.apply_async(args=[job_id, request.topics, request.max_sources_per_topic], queue="ingestion")
    INGESTION_REQUESTS.inc()
    return IngestionJob(**record)


@app.get("/v1/ingestion/jobs/{job_id}", response_model=IngestionJob, dependencies=[Depends(authorize)])
def get_bulk_ingestion(job_id: str) -> IngestionJob:
    record = JobStore().get_ingestion_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return IngestionJob(**record)


@app.get("/v1/research/{task_id}/events", dependencies=[Depends(authorize)])
async def stream_events(task_id: str):
    if not JobStore().get(task_id): raise HTTPException(status_code=404, detail="Research task not found")
    async def event_stream():
        cursor = 0
        while True:
            current = JobStore().get(task_id)
            for event in JobStore().list_events(task_id, cursor):
                cursor = event["sequence"]
                yield f"event: progress\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            if current and current["status"] in {"completed", "failed"}:
                yield "event: done\ndata: {}\n\n"
                break
            await asyncio.sleep(1)
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/v1/research/{task_id}/sources", dependencies=[Depends(authorize)])
def get_sources(task_id: str) -> list[dict]:
    return JobStore().list_sources(task_id)


@app.get("/v1/research/{task_id}/graph", dependencies=[Depends(authorize)])
def get_research_graph(task_id: str) -> dict:
    if not JobStore().get(task_id): raise HTTPException(status_code=404, detail="Research task not found")
    try:
        return ResearchGraphRepository().subgraph(task_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Graph database unavailable: {exc}")


@app.get("/v1/research/{task_id}/evaluation", response_model=EvaluationResult, dependencies=[Depends(authorize)])
def get_evaluation(task_id: str) -> EvaluationResult:
    record = JobStore().get(task_id)
    if not record: raise HTTPException(status_code=404, detail="Research task not found")
    metric = record.get("metrics") or evaluate_citations(record.get("report") or "", len(JobStore().list_sources(task_id)))
    return EvaluationResult(task_id=task_id, **metric)


@app.get("/v1/research/{task_id}/export.md", dependencies=[Depends(authorize)])
def export_markdown(task_id: str) -> Response:
    record = JobStore().get(task_id)
    if not record or not record.get("report"): raise HTTPException(status_code=404, detail="Completed report not found")
    return Response(record["report"], media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="research-{task_id}.md"'})


@app.get("/v1/research/{task_id}/export.pdf", dependencies=[Depends(authorize)])
def export_pdf(task_id: str) -> Response:
    record = JobStore().get(task_id)
    if not record or not record.get("report"): raise HTTPException(status_code=404, detail="Completed report not found")
    return Response(report_as_pdf(record["topic"], record["report"]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="research-{task_id}.pdf"'})
