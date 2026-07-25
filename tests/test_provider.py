from types import SimpleNamespace
from app import research_graph
import httpx


class FakeResponse:
    def raise_for_status(self): pass
    def json(self): return {"message": {"content": "local response"}}


def test_ollama_provider_calls_local_chat_endpoint(monkeypatch) -> None:
    settings = SimpleNamespace(llm_provider="ollama", ollama_base_url="http://ollama:11434", ollama_model="qwen", ollama_timeout_seconds=10)
    captured = {}
    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        return FakeResponse()
    monkeypatch.setattr(research_graph, "get_settings", lambda: settings)
    monkeypatch.setattr(research_graph.httpx, "post", fake_post)
    assert research_graph._llm_text("system", "prompt") == "local response"
    assert captured["url"] == "http://ollama:11434/api/chat"
    assert captured["payload"]["think"] is False


def test_ollama_provider_falls_back_on_network_error(monkeypatch) -> None:
    settings = SimpleNamespace(llm_provider="ollama", ollama_base_url="http://ollama:11434", ollama_model="qwen", ollama_timeout_seconds=10)
    monkeypatch.setattr(research_graph, "get_settings", lambda: settings)
    monkeypatch.setattr(research_graph.httpx, "post", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    assert research_graph._llm_text("system", "prompt") is None
