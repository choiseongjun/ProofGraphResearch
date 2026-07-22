from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app import main
from app.config import get_settings


class FakeStore:
    record = {"task_id": "task-1", "status": "queued", "topic": "AI", "audience": "reviewer", "depth": "brief", "report": None, "error": None, "metrics": None, "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}

    def create(self, task_id, payload):
        return self.record | {"task_id": task_id, "topic": payload["topic"], "audience": payload["audience"], "depth": payload["depth"]}

    def get(self, task_id):
        return self.record | {"task_id": task_id}


def test_dashboard_and_create_job_contract(monkeypatch) -> None:
    monkeypatch.setattr(main, "JobStore", FakeStore)
    monkeypatch.setattr(main.run_research, "delay", lambda *args: None)
    client = TestClient(main.app)
    assert client.get("/").status_code == 200
    headers = {"X-API-Key": get_settings().app_api_key} if get_settings().app_api_key else {}
    response = client.post("/v1/research", json={"topic": "AI", "audience": "reviewer", "depth": "brief"}, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_health_and_validation_contract() -> None:
    client = TestClient(main.app)
    assert client.get("/health").json()["status"] == "ok"
    headers = {"X-API-Key": get_settings().app_api_key} if get_settings().app_api_key else {}
    assert client.post("/v1/research", json={"topic": "x"}, headers=headers).status_code == 422
