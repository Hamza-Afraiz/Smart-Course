import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.certificate import Certificate


async def get_by_enrollment(
    db: AsyncSession, enrollment_id: uuid.UUID
) -> Certificate | None:
    result = await db.execute(
        select(Certificate).where(Certificate.enrollment_id == enrollment_id)
    )
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    enrollment_id: uuid.UUID,
    student_id: uuid.UUID,
    course_id: uuid.UUID,
) -> Certificate:
    cert = Certificate(
        enrollment_id=enrollment_id,
        student_id=student_id,
        course_id=course_id,
    )
    db.add(cert)
    await db.flush()
    return cert


async def list_for_student(
    db: AsyncSession, student_id: uuid.UUID, *, limit: int, offset: int
) -> list[Certificate]:
    result = await db.execute(
        select(Certificate)
        .options(joinedload(Certificate.course))
        .where(Certificate.student_id == student_id)
        .order_by(Certificate.issued_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().unique().all())
