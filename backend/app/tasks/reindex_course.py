"""Re-index a published course's lesson chunks (Celery)."""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.database import AsyncSessionLocal
from app.observability.propagation import use_traceparent
from app.services.content_indexing_service import index_course_lessons
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.reindex_course",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def reindex_course(
    self, course_id: str, traceparent: str | None = None
) -> None:
    try:
        asyncio.run(_reindex(course_id, traceparent))
    except Exception as exc:
        logger.exception("reindex_course: failed for course %s", course_id)
        raise self.retry(exc=exc) from exc


async def _reindex(course_id: str, traceparent: str | None) -> None:
    async with use_traceparent(traceparent):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                n = await index_course_lessons(session, uuid.UUID(course_id))
                logger.info("reindex_course: course=%s chunks=%d", course_id, n)
