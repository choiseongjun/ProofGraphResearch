from app.rag_repository import _chunks


def test_chunking_preserves_content_and_overlaps():
    content = "alpha " * 500
    chunks = _chunks(content, size=120, overlap=20)
    assert len(chunks) > 2
    assert chunks[0]
    assert chunks[1] in content


def test_chunking_ignores_blank_content():
    assert _chunks("  \n\t ") == []


def test_chunking_removes_postgresql_unsafe_nul_bytes():
    chunks = _chunks("evidence\x00with\x00binary fragments")
    assert chunks == ["evidence with binary fragments"]
