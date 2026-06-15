import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certificate import Certificate
from app.models.enrollment import Enrollment
from app.repositories import certificate_repo

logger = logging.getLogger(__name__)


async def issue_for_enrollment(
    db: AsyncSession, enrollment: Enrollment
) -> Certificate | None:
    """Idempotent — returns existing certificate if already issued."""
    existing = await certificate_repo.get_by_enrollment(db, enrollment.id)
    if existing is not None:
        return existing

    cert = await certificate_repo.create(
        db,
        enrollment_id=enrollment.id,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
    )
    logger.info(
        "certificate issued enrollment=%s student=%s course=%s",
        enrollment.id,
        enrollment.student_id,
        enrollment.course_id,
    )
    return cert


async def list_for_student(
    db: AsyncSession, student_id: uuid.UUID, *, limit: int, offset: int
) -> list[Certificate]:
    return await certificate_repo.list_for_student(
        db, student_id, limit=limit, offset=offset
    )
