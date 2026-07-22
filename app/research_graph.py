"""LangGraph orchestration for Planner → Search → Compression → Writer → Critic."""
from __future__ import annotations

import json
import re
import httpx
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from app.config import get_settings
from app.knowledge_base import search_internal_knowledge
from app.graph_repository import ResearchGraphRepository

logger = logging.getLogger(__name__)


class ResearchState(TypedDict, total=False):
    topic: str
    audience: str
    depth: str
    outline: list[str]
    queries: list[str]
    sources: list[dict[str, str]]
    compressed_context: str
    draft: str
    critique: str
    revision_count: int
    task_id: str
    relationship_context: str


def _is_local_provider() -> bool:
    return get_settings().llm_provider.lower() == "ollama"


def _llm_text(system: str, prompt: str) -> str | None:
    """Provider adapter: OpenAI cloud or locally hosted Ollama."""
    settings = get_settings()
    if settings.llm_provider.lower() == "ollama":
        try:
            response = httpx.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json={"model": settings.ollama_model, "stream": False, "think": False, "messages": [{"role": "system", "content": f"{system}\n/no_think"}, {"role": "user", "content": prompt}], "options": {"temperature": 0.2, "num_predict": 512}},
                timeout=settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except httpx.HTTPError as exc:
            logger.warning("Ollama request failed; using deterministic fallback: %s", exc)
            return None
    if not settings.openai_api_key:
        return None
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(model=settings.openai_model, temperature=0.2, api_key=settings.openai_api_key)
    return model.invoke([( "system", system), ("human", prompt)]).content


def _json_from_text(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def planner(state: ResearchState) -> dict[str, Any]:
    topic, depth = state["topic"], state["depth"]
    if _is_local_provider():
        return {"outline": ["핵심 요약", "시장 및 현황", "주요 동인과 사례", "리스크 및 한계", "시사점과 권고"], "queries": [f"{topic} latest statistics", f"{topic} market analysis", f"{topic} regulations risks", f"{topic} case study"], "revision_count": 0}
    answer = _llm_text(
        "You are a research planner. Return JSON only. Make a non-overlapping report outline and focused web search queries in Korean.",
        f"Topic: {topic}\nDepth: {depth}\nReturn {{\"outline\": [..], \"queries\": [..]}}. Use 3-5 queries.",
    )
    parsed = _json_from_text(answer) if answer else None
    if parsed and isinstance(parsed.get("outline"), list) and isinstance(parsed.get("queries"), list):
        return {"outline": parsed["outline"], "queries": parsed["queries"], "revision_count": 0}
    return {
        "outline": ["핵심 요약", "시장 및 현황", "주요 동인과 사례", "리스크 및 한계", "시사점과 권고"],
        "queries": [f"{topic} latest statistics", f"{topic} market analysis", f"{topic} regulations risks", f"{topic} case study"],
        "revision_count": 0,
    }


def _search_one(query: str) -> list[dict[str, str]]:
    settings = get_settings()
    if settings.tavily_api_key:
        from tavily import TavilyClient
        results = TavilyClient(api_key=settings.tavily_api_key).search(query=query, max_results=4)["results"]
        return [{"title": r.get("title", "Untitled"), "url": r.get("url", ""), "content": r.get("content", "")} for r in results]
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=4)
        return [{"title": r.get("title", "Untitled"), "url": r.get("href", ""), "content": r.get("body", "")} for r in results]
    except Exception:
        # The graph is still demonstrable in an offline development environment.
        return [{"title": f"검색 대기: {query}", "url": "", "content": "검색 API 키 또는 네트워크 연결을 설정하면 근거 자료가 수집됩니다."}]


def searcher(state: ResearchState) -> dict[str, Any]:
    seen: set[str] = set()
    sources: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(state["queries"]))) as executor:
        futures = [executor.submit(_search_one, q) for q in state["queries"]]
        for future in as_completed(futures):
            for item in future.result():
                url = item["url"] or item["title"]
                if url not in seen:
                    seen.add(url)
                    sources.append(item)
    # Internal knowledge is a separate evidence channel (e.g. exported company reports).
    for query in state["queries"]:
        for item in search_internal_knowledge(query):
            key = item["title"] + item["content"][:80]
            if key not in seen:
                seen.add(key)
                sources.append(item)
    return {"sources": sources}


def compressor(state: ResearchState) -> dict[str, Any]:
    """Compression boundary: only compact, attributable evidence reaches the writer."""
    evidence = "\n".join(
        f"[{i + 1}] {s['title']} | {s['url']}\n{s['content'][:900]}"
        for i, s in enumerate(state["sources"][:12])
    )
    if _is_local_provider():
        return {"compressed_context": evidence[:6000]}
    answer = _llm_text(
        "Compress research evidence without inventing facts. Preserve source numbers, concrete numbers, dates, caveats, and disagreements. Write Korean bullet points.",
        f"Topic: {state['topic']}\nEvidence:\n{evidence}",
    )
    # Deterministic truncation protects the writer's context even on a failed LLM compression call.
    return {"compressed_context": (answer or evidence)[:9000]}


def relationship_mapper(state: ResearchState) -> dict[str, Any]:
    """Builds a Neo4j provenance graph from sources and extracted entities."""
    sample = "\n".join(f"[{index + 1}] {source['title']}: {source['content'][:180]}" for index, source in enumerate(state["sources"][:10]))
    answer = None if _is_local_provider() else _llm_text(
        "Return JSON only. Extract an evidence graph: entities(name,type), mentions(source_number,entity), relationships(source,target,type,evidence).",
        f"Topic: {state['topic']}\nSources:\n{sample}\nReturn {{\"entities\":[],\"mentions\":[],\"relationships\":[]}}.",
    )
    parsed = _json_from_text(answer) if answer else None
    if not parsed:
        fallback_entities = [{"name": state["topic"], "type": "topic"}]
        fallback_relations = []
        for source in state["sources"][:10]:
            evidence_entity = source["title"][:120]
            fallback_entities.append({"name": evidence_entity, "type": "evidence_subject"})
            fallback_relations.append({"source": state["topic"], "target": evidence_entity, "type": "HAS_EVIDENCE", "evidence": source.get("url", "")})
        parsed = {"entities": fallback_entities, "mentions": [], "relationships": fallback_relations}
    source_keys = [ResearchGraphRepository._source_key(item) for item in state["sources"]]
    mentions = []
    for item in parsed.get("mentions", []):
        index = int(item.get("source_number", 0)) - 1
        if 0 <= index < len(source_keys) and item.get("entity"):
            mentions.append({"source_key": source_keys[index], "entity": item["entity"]})
    for source_key in source_keys:
        mentions.append({"source_key": source_key, "entity": state["topic"]})
    entities = [item for item in parsed.get("entities", []) if item.get("name")]
    if not any(item["name"] == state["topic"] for item in entities):
        entities.append({"name": state["topic"], "type": "topic"})
    try:
        relations = [item for item in parsed.get("relationships", []) if item.get("source") and item.get("target") and item.get("type")]
        summary = ResearchGraphRepository().index_research(state["task_id"], state["topic"], state["sources"], {"entities": entities, "mentions": mentions, "relationships": relations})
        return {"relationship_context": f"Relationship graph: {summary['entities']} entities, {summary['relations']} relations, {summary['sources']} sources."}
    except Exception:
        return {"relationship_context": "Relationship graph persistence was unavailable."}


def writer(state: ResearchState) -> dict[str, Any]:
    prompt = f"""주제: {state['topic']}
독자: {state['audience']}
목차: {json.dumps(state['outline'], ensure_ascii=False)}
압축된 근거:\n{state['compressed_context']}
이전 비평: {state.get('critique', '없음')}

근거에 없는 사실은 단정하지 말고, 한국어 Markdown 보고서를 작성하세요. 1) 경영진 요약 2) 목차별 분석 3) 리스크/한계 4) 실행 권고 5) 출처 목록을 포함하고 문장에 [번호]로 근거를 표시하세요."""
    answer = _llm_text("You are a rigorous research report writer.", prompt)
    if answer:
        return {"draft": answer}
    return {"draft": f"# {state['topic']}\n\n## 경영진 요약\n검색 및 모델 API 설정 후 근거 기반 보고서가 생성됩니다.\n\n## 수집 근거\n{state['compressed_context']}"}


def critic(state: ResearchState) -> dict[str, Any]:
    if _is_local_provider():
        return {"critique": "READY"}
    answer = _llm_text(
        "You are a strict research editor. Identify unsupported claims, missing counterarguments, structure issues, and actionable edits. End with exactly READY or REVISE.",
        f"Evidence:\n{state['compressed_context']}\n\nDraft:\n{state['draft']}",
    )
    return {"critique": answer or "READY"}


def route_after_critic(state: ResearchState) -> str:
    needs_revision = "REVISE" in state.get("critique", "") and state["revision_count"] < get_settings().max_revisions
    return "revise" if needs_revision else "done"


def increment_revision(state: ResearchState) -> dict[str, Any]:
    return {"revision_count": state["revision_count"] + 1}


def build_research_graph(on_event: Callable[[str, str, dict[str, Any]], None] | None = None):
    graph = StateGraph(ResearchState)
    def instrument(name: str, function: Callable[[ResearchState], dict[str, Any]]):
        def wrapped(state: ResearchState) -> dict[str, Any]:
            if on_event: on_event(name, "시작", {})
            started = time.perf_counter()
            result = function(state)
            details = {"queries": len(result.get("queries", [])), "sources": len(result.get("sources", [])), "revision": result.get("revision_count", 0)}
            details["duration_ms"] = round((time.perf_counter() - started) * 1000)
            if on_event: on_event(name, "완료", details)
            return result
        return wrapped
    graph.add_node("planner", instrument("planner", planner))
    graph.add_node("searcher", instrument("searcher", searcher))
    graph.add_node("compressor", instrument("compression", compressor))
    graph.add_node("relationship_mapper", instrument("graph_mapper", relationship_mapper))
    graph.add_node("writer", instrument("writer", writer))
    graph.add_node("critic", instrument("critic", critic))
    graph.add_node("increment_revision", increment_revision)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "searcher")
    graph.add_edge("searcher", "compressor")
    graph.add_edge("compressor", "relationship_mapper")
    graph.add_edge("relationship_mapper", "writer")
    graph.add_edge("writer", "critic")
    graph.add_conditional_edges("critic", route_after_critic, {"revise": "increment_revision", "done": END})
    graph.add_edge("increment_revision", "writer")
    return graph.compile()
