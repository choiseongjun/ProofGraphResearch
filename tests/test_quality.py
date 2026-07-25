from app.quality import evaluate_citations


def test_citation_evaluation_flags_unknown_source() -> None:
    result = evaluate_citations("사실 [1]\n잘못된 인용 [3]", 1)
    assert result["invalid_citations"] == [3]
    assert result["citation_score"] < 100


def test_citation_evaluation_accepts_known_source() -> None:
    result = evaluate_citations("사실 [1]", 1)
    assert result["invalid_citations"] == []
    assert result["citation_score"] > 0


def test_citation_evaluation_handles_report_without_citations() -> None:
    result = evaluate_citations("근거 없는 문장", 3)
    assert result["citation_score"] == 0
    assert result["cited_references"] == 0
