from unittest.mock import Mock

from app.config import get_settings
from app.rag_repository import RagRepository


def test_qdrant_search_returns_normalized_rag_result(monkeypatch):
    monkeypatch.setenv("VECTOR_BACKEND", "qdrant")
    get_settings.cache_clear()
    repository = RagRepository.__new__(RagRepository)
    client = Mock()
    client.collection_exists.return_value = True
    point = Mock()
    point.payload = {"title": "Evidence", "url": "https://example.com", "content": "content", "metadata": {"version": 1}}
    point.score = 0.91
    client.query_points.return_value.points = [point]
    repository._qdrant_client = lambda: client
    result = repository._search_qdrant([0.1, 0.2], 5)
    assert result == [{"title": "Evidence", "url": "https://example.com", "content": "content", "metadata": {"version": 1}, "score": 0.91}]
    get_settings.cache_clear()
