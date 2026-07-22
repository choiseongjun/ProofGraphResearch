"""Neo4j provenance graph for relationship-aware research retrieval."""
from __future__ import annotations

import hashlib
from typing import Any
from neo4j import GraphDatabase
from app.config import get_settings


class ResearchGraphRepository:
    def __init__(self) -> None:
        settings = get_settings()
        self.driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))

    @staticmethod
    def _source_key(source: dict[str, str]) -> str:
        return hashlib.sha256((source.get("url") or source["title"]).encode()).hexdigest()

    def index_research(self, task_id: str, topic: str, sources: list[dict[str, str]], mapping: dict[str, Any]) -> dict[str, int]:
        entities = mapping.get("entities", [])
        mentions = mapping.get("mentions", [])
        relations = mapping.get("relationships", [])
        indexed_sources = [{"key": self._source_key(item), "title": item["title"], "url": item.get("url", "")} for item in sources]
        with self.driver.session() as session:
            session.run("MERGE (r:Research {task_id:$task_id}) SET r.topic=$topic", task_id=task_id, topic=topic)
            session.run("UNWIND $sources AS source MERGE (s:Source {source_key:source.key}) SET s.title=source.title, s.url=source.url WITH s MATCH (r:Research {task_id:$task_id}) MERGE (r)-[:USES_SOURCE]->(s)", task_id=task_id, sources=indexed_sources)
            session.run("UNWIND $entities AS entity MERGE (e:Entity {name:entity.name}) SET e.type=coalesce(entity.type, 'unknown')", entities=entities)
            session.run("UNWIND $mentions AS mention MATCH (s:Source {source_key:mention.source_key}) MATCH (e:Entity {name:mention.entity}) MERGE (s)-[:MENTIONS]->(e)", mentions=mentions)
            session.run("UNWIND $relations AS relation MATCH (a:Entity {name:relation.source}) MATCH (b:Entity {name:relation.target}) MERGE (a)-[r:RELATES_TO {relation_type:relation.type}]->(b) SET r.evidence=relation.evidence", relations=relations)
        return {"sources": len(indexed_sources), "entities": len(entities), "relations": len(relations)}

    def subgraph(self, task_id: str) -> dict[str, Any]:
        with self.driver.session() as session:
            rows = session.run("MATCH (r:Research {task_id:$task_id})-[:USES_SOURCE]->(s:Source) OPTIONAL MATCH (s)-[:MENTIONS]->(e:Entity) RETURN s.title AS source, s.url AS url, collect(DISTINCT {name:e.name, type:e.type}) AS entities ORDER BY source", task_id=task_id)
            source_nodes = [dict(row) for row in rows]
            relations = [dict(row) for row in session.run("MATCH (r:Research {task_id:$task_id})-[:USES_SOURCE]->(:Source)-[:MENTIONS]->(a:Entity) MATCH (a)-[edge:RELATES_TO]->(b:Entity) RETURN DISTINCT a.name AS source, edge.relation_type AS type, b.name AS target, edge.evidence AS evidence LIMIT 50", task_id=task_id)]
        return {"sources": source_nodes, "relationships": relations}
