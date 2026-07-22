import time
from app.celery_app import celery_app
from app.config import get_settings
from app.research_graph import build_research_graph
from app.store import JobStore
from app.quality import evaluate_citations
from app.artifact_store import upload_markdown_report


@celery_app.task(bind=True, name="research.run", max_retries=2)
def run_research(self, task_id: str, payload: dict) -> dict:
    store = JobStore()
    store.update(task_id, status="running", attempt_count=self.request.retries + 1)
    store.append_event(task_id, "running", "Worker가 리서치 실행을 시작했습니다.")
    started = time.perf_counter()
    agent_timings: dict[str, int] = {}
    try:
        def emit(phase, message, details):
            if message == "완료" and details.get("duration_ms") is not None: agent_timings[phase] = details["duration_ms"]
            store.append_event(task_id, phase, message, details)
        final_state = build_research_graph(emit).invoke({**payload, "task_id": task_id})
        store.save_sources(task_id, final_state.get("sources", []))
        metrics = evaluate_citations(final_state["draft"], len(final_state.get("sources", [])))
        try:
            artifact_uri = upload_markdown_report(task_id, payload["topic"], final_state["draft"])
            if artifact_uri:
                metrics["artifact_uri"] = artifact_uri
                store.append_event(task_id, "artifact", "Report artifact uploaded.", {"uri": artifact_uri})
        except Exception as artifact_error:
            # Research completion must not depend on optional artifact storage.
            store.append_event(task_id, "artifact", "Report artifact upload skipped.", {"error": str(artifact_error)})
        settings = get_settings()
        metrics.update({"duration_ms": round((time.perf_counter() - started) * 1000), "provider": settings.llm_provider, "model": settings.ollama_model if settings.llm_provider.lower() == "ollama" else settings.openai_model, "agent_durations_ms": agent_timings})
        store.update(task_id, status="completed", report=final_state["draft"], metrics=metrics)
        store.append_event(task_id, "completed", "보고서와 인용 품질 평가가 저장되었습니다.", metrics)
        return {"task_id": task_id, "report": final_state["draft"]}
    except Exception as exc:
        if self.request.retries < self.max_retries:
            store.update(task_id, status="queued", error=None)
            store.append_event(task_id, "retrying", f"일시 오류로 {self.request.retries + 1}회 재시도합니다.")
            raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))
        store.update(task_id, status="failed", error=str(exc))
        store.append_event(task_id, "failed", "작업 실행 중 오류가 발생했습니다.")
        raise
