"""Welcome-email Celery task — stub.

For now this is a logger.info, not a real SMTP send. The point is to prove
the task-execution half of the pipeline: a Celery worker pulls this task off
RabbitMQ, fetches what it needs from Postgres, and "delivers" the email.

When real email is wired in (SES / SendGrid / Mailgun), the only change is
swapping the logger.info for the client call — the surrounding plumbing
(enqueue, retry, idempotency at the consumer level) stays.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import AsyncSessionLocal
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.send_welcome_email",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_welcome_email(self, enrollment_id: str) -> None:
    """Celery is sync; we bridge to our async DB layer via asyncio.run."""
    try:
        asyncio.run(_send(enrollment_id))
    except Exception as exc:
        logger.exception("welcome_email: error for enrollment %s", enrollment_id)
        # Re-raise to engage Celery's retry policy (max_retries above)
        raise self.retry(exc=exc) from exc


async def _send(enrollment_id: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Enrollment)
            .options(joinedload(Enrollment.student), joinedload(Enrollment.course))
            .where(Enrollment.id == enrollment_id)
        )
        enrollment = result.scalar_one_or_none()
        if enrollment is None:
            # Enrollment was deleted between event emission and task execution.
            # Don't retry — this is a permanent absence, not a transient failure.
            logger.warning(
                "welcome_email: enrollment %s no longer exists; dropping task",
                enrollment_id,
            )
            return

        # Stub send. Production replacement: an SES/SendGrid client call.
        logger.info(
            "📧 [stub] welcome-email → %s (%s) — enrolled in %r",
            enrollment.student.email,
            enrollment.student.full_name or "—",
            enrollment.course.title,
        )
