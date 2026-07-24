"use client";

import { FormEvent, useMemo, useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
type Job = { task_id: string; status: string; report?: string; error?: string; metrics?: Record<string, unknown> };
type SearchResult = { title: string; url?: string; content: string; score: number };
type Workflow = { id: string; version: string; quality_gate: string; steps: { id: string; name: string; responsibility: string }[] };
type Source = { source_number: number; title: string; url?: string; content?: string; source_type: string };

export default function Dashboard() {
  const [apiKey, setApiKey] = useState("");
  const [topic, setTopic] = useState("2026년 한국 AI 에이전트 시장 전망");
  const [crawlTopic, setCrawlTopic] = useState("2026년 한국 AI 에이전트 시장 전망");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("준비되었습니다.");
  const [job, setJob] = useState<Job | null>(null);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [evaluation, setEvaluation] = useState<Record<string, unknown> | null>(null);
  const [graph, setGraph] = useState<Record<string, unknown> | null>(null);
  const headers = useMemo<Record<string, string>>(() => {
    const value: Record<string, string> = { "Content-Type": "application/json" };
    if (apiKey) value["X-API-Key"] = apiKey;
    return value;
  }, [apiKey]);

  async function research(event: FormEvent) {
    event.preventDefault(); setMessage("워크플로 실행을 요청했습니다.");
    const response = await fetch(`${apiBase}/v1/research`, { method: "POST", headers, body: JSON.stringify({ topic, audience: "신사업 임원", depth: "deep" }) });
    const data = await response.json();
    if (!response.ok) return setMessage(data.detail || "요청에 실패했습니다.");
    setJob(data); poll(data.task_id);
  }
  async function poll(id: string) {
    const timer = window.setInterval(async () => {
      const response = await fetch(`${apiBase}/v1/research/${id}`, { headers }); const data = await response.json();
      if (response.ok) setJob(data);
      if (data.status === "completed" || data.status === "failed") { window.clearInterval(timer); setMessage(data.status === "completed" ? "워크플로가 완료됐습니다. 근거를 RAG에 누적했습니다." : data.error || "워크플로 실행에 실패했습니다."); }
    }, 1600);
  }
  async function crawl(event: FormEvent) {
    event.preventDefault(); setMessage("공개 웹 근거를 탐색·수집·임베딩하고 있습니다.");
    const response = await fetch(`${apiBase}/v1/knowledge/crawl`, { method: "POST", headers, body: JSON.stringify({ topic: crawlTopic, max_sources: 6 }) }); const data = await response.json();
    setMessage(response.ok ? `${data.indexed_documents}개 문서와 ${data.indexed_chunks}개 청크를 색인했습니다.` : data.detail || "자동 수집에 실패했습니다.");
  }
  async function search(event: FormEvent) {
    event.preventDefault(); const response = await fetch(`${apiBase}/v1/knowledge/search`, { method: "POST", headers, body: JSON.stringify({ query, limit: 5 }) }); const data = await response.json();
    if (response.ok) setResults(data.results); else setMessage(data.detail || "벡터 검색에 실패했습니다.");
  }
  async function showWorkflow() {
    const response = await fetch(`${apiBase}/v1/workflows/evidence-first-research`, { headers }); const data = await response.json();
    if (response.ok) setWorkflow(data); else setMessage(data.detail || "워크플로 정의를 불러오지 못했습니다.");
  }
  async function inspectRun(kind: "sources" | "evaluation" | "graph") {
    if (!job) return;
    const response = await fetch(`${apiBase}/v1/research/${job.task_id}/${kind}`, { headers }); const data = await response.json();
    if (!response.ok) return setMessage(data.detail || "실행 결과를 불러오지 못했습니다.");
    if (kind === "sources") setSources(data); else if (kind === "evaluation") setEvaluation(data); else setGraph(data);
  }
  function exportReport(format: "md" | "pdf") {
    if (!job) return;
    const key = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";
    window.open(`${apiBase}/v1/research/${job.task_id}/export.${format}${key}`, "_blank", "noopener,noreferrer");
  }

  return <main>
    <header><p className="eyebrow">PROOFGRAPH / 워크플로 AI</p><h1>근거 중심 AI 워크플로 런타임</h1><p>LangGraph 오케스트레이션 · pgvector RAG · Neo4j 근거 그래프 · LocalStack 아티팩트 · QLoRA 파이프라인</p></header>
    <section className="grid">
      <article className="wide"><h2>워크플로 계약</h2><p>각 실행은 단계, 데이터 계약, 실패 정책, 품질 게이트로 관리됩니다.</p><button onClick={showWorkflow}>워크플로 정의 보기</button>{workflow && <div className="workflow"><b>{workflow.id} / v{workflow.version}</b><p>{workflow.quality_gate}</p>{workflow.steps.map(step => <div key={step.id}><code>{step.id}</code><strong>{step.name}</strong><span>{step.responsibility}</span></div>)}</div>}</article>
      <article><h2>리서치 워크플로 실행</h2><form onSubmit={research}><label>API 키 (선택)<input value={apiKey} onChange={e => setApiKey(e.target.value)} type="password" /></label><label>비즈니스 주제<textarea value={topic} onChange={e => setTopic(e.target.value)} /></label><button>워크플로 실행 시작</button></form>{job && <div className="status"><b>{job.status.toUpperCase()}</b><code>{job.task_id}</code>{job.metrics && <pre>{JSON.stringify(job.metrics, null, 2)}</pre>}</div>}</article>
      <article><h2>RAG 자동 수집·색인</h2><p>주제만 입력하면 시스템이 공개 근거를 탐색하고, 본문 수집·청킹·임베딩을 자동 수행합니다.</p><form onSubmit={crawl}><label>수집 주제<input required value={crawlTopic} onChange={e => setCrawlTopic(e.target.value)} /></label><button>근거 자동 수집·색인</button></form></article>
      <article className="wide"><h2>벡터 검색</h2><form className="inline" onSubmit={search}><input required value={query} onChange={e => setQuery(e.target.value)} placeholder="누적 근거를 의미 기반으로 검색" /><button>검색</button></form><div className="results">{results.map((item, index) => <div key={index}><b>{item.title}</b><small> 유사도 {Number(item.score).toFixed(3)}</small><p>{item.content}</p>{item.url && <a href={item.url} target="_blank">원문 열기</a>}</div>)}</div></article>
      <article className="wide"><h2>런타임 상태</h2><p className="message">{message}</p>{job?.report && <><div className="next-actions"><b>다음 단계</b><span>보고서의 근거와 품질을 검증한 뒤, Markdown 또는 PDF로 내보내세요.</span><button onClick={() => inspectRun("sources")}>출처 확인</button><button onClick={() => inspectRun("evaluation")}>품질 점수 확인</button><button onClick={() => inspectRun("graph")}>근거 그래프 확인</button><button onClick={() => exportReport("md")}>Markdown 내보내기</button><button onClick={() => exportReport("pdf")}>PDF 내보내기</button></div><pre className="report">{job.report}</pre></>}{sources.length > 0 && <div className="inspection"><h3>수집 출처</h3>{sources.map(source => <div key={source.source_number}><b>[{source.source_number}] {source.title}</b>{source.url && <a href={source.url} target="_blank">원문 열기</a>}<p>{source.content?.slice(0, 400)}</p></div>)}</div>}{evaluation && <div className="inspection"><h3>품질 평가</h3><pre>{JSON.stringify(evaluation, null, 2)}</pre></div>}{graph && <div className="inspection"><h3>근거 그래프</h3><pre>{JSON.stringify(graph, null, 2)}</pre></div>}</article>
    </section>
  </main>;
}
