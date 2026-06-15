"""Welcome-email Celery task — sends via SMTP (Mailhog in dev)."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import AsyncSessionLocal
from app.models.enrollment import Enrollment
from app.observability.propagation import use_traceparent
from app.services.email_service import send_email
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.send_welcome_email",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_welcome_email(
    self, enrollment_id: str, traceparent: str | None = None
) -> None:
    """Celery is sync; we bridge to our async DB layer via asyncio.run."""
    try:
        asyncio.run(_send(enrollment_id, traceparent))
    except Exception as exc:
        logger.exception("welcome_email: error for enrollment %s", enrollment_id)
        raise self.retry(exc=exc) from exc


async def _send(enrollment_id: str, traceparent: str | None) -> None:
    async with use_traceparent(traceparent):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Enrollment)
                .options(
                    joinedload(Enrollment.student),
                    joinedload(Enrollment.course),
                )
                .where(Enrollment.id == enrollment_id)
            )
            enrollment = result.scalar_one_or_none()
            if enrollment is None:
                logger.warning(
                    "welcome_email: enrollment %s no longer exists; dropping task",
                    enrollment_id,
                )
                return

            student = enrollment.student
            course = enrollment.course
            subject = f"Welcome to {course.title}!"
            body = (
                f"Hi {student.full_name or student.email},\n\n"
                f"You are enrolled in {course.title!r}. "
                f"Open SmartCourse to start learning.\n\n"
                f"— SmartCourse"
            )
            await send_email(to=student.email, subject=subject, body=body)
            logger.info(
                "welcome_email sent → %s enrolled in %r",
                student.email,
                course.title,
            )
