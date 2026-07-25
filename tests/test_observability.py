from fastapi.testclient import TestClient

from app.main import app


def test_prometheus_metrics_are_exposed_without_api_key():
    response = TestClient(app).get("/metrics")
    assert response.status_code == 200
    assert "proofgraph_http_requests_total" in response.text
    assert "proofgraph_knowledge_chunks" in response.text
