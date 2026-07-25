"""Optional report artifact storage backed by S3 or LocalStack S3."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from app.config import get_settings


def upload_markdown_report(task_id: str, topic: str, report: str) -> str | None:
    """Store a finished report only when artifact storage was explicitly enabled."""
    settings = get_settings()
    if not settings.artifact_storage_enabled:
        return None

    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    key = f"reports/{task_id}.md"
    client.put_object(
        Bucket=settings.artifact_bucket,
        Key=key,
        Body=report.encode("utf-8"),
        ContentType="text/markdown; charset=utf-8",
        Metadata={"topic": topic[:512]},
    )
    return f"s3://{settings.artifact_bucket}/{key}"


def archive_source_document(document: dict) -> str | None:
    """Persist the collected source payload to S3/LocalStack before vector indexing."""
    settings = get_settings()
    if not settings.raw_document_storage_enabled:
        return None
    raw = document.get("raw_content") or document.get("content", "")
    if isinstance(raw, str):
        raw_bytes = raw.encode("utf-8", errors="replace")
        content_type = "text/plain; charset=utf-8"
    else:
        raw_bytes = bytes(raw)
        content_type = document.get("content_type") or "application/octet-stream"
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    key = f"sources/{day}/{checksum}/source"
    manifest_key = f"sources/{day}/{checksum}/manifest.json"
    import boto3
    client = boto3.client("s3", endpoint_url=settings.aws_endpoint_url, region_name=settings.aws_region, aws_access_key_id=settings.aws_access_key_id, aws_secret_access_key=settings.aws_secret_access_key)
    client.put_object(Bucket=settings.raw_document_bucket, Key=key, Body=raw_bytes, ContentType=content_type)
    manifest = {"title": document.get("title"), "url": document.get("url"), "checksum": checksum, "collected_at": datetime.now(timezone.utc).isoformat(), "content_type": content_type}
    client.put_object(Bucket=settings.raw_document_bucket, Key=manifest_key, Body=json.dumps(manifest, ensure_ascii=False).encode("utf-8"), ContentType="application/json")
    return f"s3://{settings.raw_document_bucket}/{key}"
