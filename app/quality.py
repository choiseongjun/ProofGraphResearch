import re
from typing import Any


def evaluate_citations(report: str, source_count: int) -> dict[str, Any]:
    """Deterministic, explainable guardrail for report citations."""
    cited = sorted({int(item) for item in re.findall(r"\[(\d+)]", report)})
    invalid = [number for number in cited if number < 1 or number > source_count]
    paragraphs = [line for line in report.splitlines() if line.strip() and not line.startswith("#")]
    cited_paragraphs = sum(1 for paragraph in paragraphs if re.search(r"\[\d+]", paragraph))
    coverage = cited_paragraphs / max(1, len(paragraphs))
    score = max(0, min(100, round(coverage * 70 + min(1, len(cited) / max(1, source_count)) * 30 - len(invalid) * 15)))
    return {"citation_score": score, "cited_references": len(cited), "source_count": source_count, "invalid_citations": invalid, "summary": "인용 범위와 유효한 출처 번호를 기준으로 계산한 결정론적 품질 지표입니다."}
