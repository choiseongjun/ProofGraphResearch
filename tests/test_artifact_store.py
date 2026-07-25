from unittest.mock import Mock, patch

from app.artifact_store import archive_source_document, upload_markdown_report
from app.config import get_settings


def test_artifact_upload_is_off_by_default(monkeypatch):
    monkeypatch.setenv("ARTIFACT_STORAGE_ENABLED", "false")
    get_settings.cache_clear()
    assert upload_markdown_report("task-1", "topic", "report") is None
    get_settings.cache_clear()


def test_artifact_upload_uses_configured_s3(monkeypatch):
    monkeypatch.setenv("ARTIFACT_STORAGE_ENABLED", "true")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    get_settings.cache_clear()
    client = Mock()
    with patch("boto3.client", return_value=client) as create_client:
        uri = upload_markdown_report("task-1", "topic", "report")
    assert uri == "s3://proofgraph-reports/reports/task-1.md"
    assert create_client.call_args.kwargs["endpoint_url"] == "http://localhost:4566"
    assert client.put_object.call_args.kwargs["Key"] == "reports/task-1.md"
    get_settings.cache_clear()


def test_raw_source_archive_stores_payload_and_manifest(monkeypatch):
    monkeypatch.setenv("RAW_DOCUMENT_STORAGE_ENABLED", "true")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    get_settings.cache_clear()
    client = Mock()
    with patch("boto3.client", return_value=client):
        uri = archive_source_document(
            {
                "title": "Evidence PDF",
                "url": "https://example.com/evidence.pdf",
                "raw_content": b"%PDF-1.4\\x00binary",
                "content_type": "application/pdf",
            }
        )
    assert uri is not None
    assert uri.startswith("s3://proofgraph-raw/sources/")
    assert client.put_object.call_count == 2
    first_call = client.put_object.call_args_list[0].kwargs
    second_call = client.put_object.call_args_list[1].kwargs
    assert first_call["Bucket"] == "proofgraph-raw"
    assert first_call["ContentType"] == "application/pdf"
    assert second_call["Key"].endswith("/manifest.json")
    get_settings.cache_clear()
