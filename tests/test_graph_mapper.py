from app import research_graph


class FakeGraphRepository:
    @staticmethod
    def _source_key(source: dict[str, str]) -> str:
        return source["url"]

    def index_research(self, task_id, topic, sources, mapping):
        assert task_id == "task-1"
        assert mapping["entities"]
        assert mapping["relationships"]
        return {"sources": len(sources), "entities": len(mapping["entities"]), "relations": len(mapping["relationships"])}


def test_graph_mapper_creates_fallback_relationships(monkeypatch) -> None:
    monkeypatch.setattr(research_graph, "ResearchGraphRepository", FakeGraphRepository)
    monkeypatch.setattr(research_graph, "_llm_text", lambda *_: None)
    result = research_graph.relationship_mapper({"task_id": "task-1", "topic": "AI agents", "sources": [{"title": "OpenAI", "url": "https://openai.com", "content": "Agent research"}]})
    assert "1 relations" in result["relationship_context"]
