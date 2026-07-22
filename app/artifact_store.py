"""Optional report artifact storage backed by S3 or LocalStack S3."""

from __future__ import annotations

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
