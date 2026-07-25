"""Explicit workflow contracts: reusable AI system design above individual agents."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    name: str
    responsibility: str
    input_contract: str
    output_contract: str
    failure_policy: str


@dataclass(frozen=True)
class WorkflowDefinition:
    id: str
    version: str
    description: str
    quality_gate: str
    steps: tuple[WorkflowStep, ...]

    def as_dict(self) -> dict:
        value = asdict(self)
        value["steps"] = [asdict(step) for step in self.steps]
        return value


RESEARCH_WORKFLOW = WorkflowDefinition(
    id="evidence-first-research",
    version="2.0",
    description="주제를 인용 가능한 임원용 보고서와 재사용 가능한 지식 자산으로 전환하는 내구성 있는 근거 워크플로입니다.",
    quality_gate="인용 품질, 출처 범위, 비평 단계가 완료되어야 실행을 완료 처리합니다.",
    steps=(
        WorkflowStep("plan", "계획 수립", "비즈니스 질문을 보고서 목차와 검색 계획으로 분해합니다.", "주제, 독자, 깊이", "목차, 검색 쿼리", "결정론적 대체 로직"),
        WorkflowStep("collect", "근거 수집", "최신 웹 근거와 내부 지식을 수집합니다.", "검색 쿼리", "추적 가능한 출처", "수집 가능한 출처로 계속 진행"),
        WorkflowStep("retrieve", "RAG 검색", "pgvector RAG에서 의미적으로 유사한 기존 근거를 찾습니다.", "주제", "순위화된 재사용 근거", "벡터 서비스 오류 시 건너뜀"),
        WorkflowStep("compress", "컨텍스트 압축", "출처 식별자를 유지한 제한된 근거 컨텍스트를 만듭니다.", "출처", "압축 근거 컨텍스트", "결정론적 길이 제한"),
        WorkflowStep("map", "관계 매핑", "출처·엔티티 관계를 Neo4j에 저장합니다.", "출처, 엔티티", "근거 그래프 요약", "그래프 서비스 오류 시 계속 진행"),
        WorkflowStep("write", "보고서 작성", "입력 근거만 바탕으로 보고서를 작성합니다.", "목차, 압축 컨텍스트", "인용 Markdown 초안", "로컬 결정론적 대체 로직"),
        WorkflowStep("review", "비평·검토", "근거 부족, 구조, 반대 근거 누락을 점검합니다.", "초안, 근거", "READY 또는 REVISE", "최대 수정 횟수 정책"),
        WorkflowStep("learn", "지식 축적", "다음 검색에 쓰일 출처 청크와 보고서 아티팩트를 저장합니다.", "출처, 최종 보고서", "RAG 청크, S3 URI", "비차단 부수 효과"),
    ),
)


def list_workflows() -> list[dict]:
    return [RESEARCH_WORKFLOW.as_dict()]
