from celery import Celery
from app.config import get_settings

settings = get_settings()
celery_app = Celery(
    "deep_research",
    broker=settings.redis_url,
    include=["app.tasks"],  # Register `research.run` in every worker process.
)
# PostgreSQL is the source of truth for job state/results; Redis is only Celery's broker.
celery_app.conf.update(task_track_started=True, timezone="Asia/Seoul")
