import pytest
from pydantic import ValidationError

from app.schemas import KnowledgeDocumentRequest


def test_knowledge_document_accepts_url_without_manual_content():
    document = KnowledgeDocumentRequest(url="https://example.com/report")
    assert document.url == "https://example.com/report"


def test_knowledge_document_requires_content_or_url():
    with pytest.raises(ValidationError):
        KnowledgeDocumentRequest()
