import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus


async def lock_course_for_enrollment(
    db: AsyncSession, course_id: uuid.UUID
) -> Course | None:
    """
    Acquire a row-level lock on the course inside the current transaction.
    Serializes concurrent enrollment attempts for the same course so the
    capacity check below cannot race. Lock released on commit/rollback.
    """
    result = await db.execute(
        select(Course).where(Course.id == course_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def count_active(db: AsyncSession, course_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Enrollment)
        .where(
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.active,
        )
    )
    return int(result.scalar_one())


async def get_by_id(db: AsyncSession, enrollment_id: uuid.UUID) -> Enrollment | None:
    result = await db.execute(
        select(Enrollment).where(Enrollment.id == enrollment_id)
    )
    return result.scalar_one_or_none()


async def get_by_student_and_course(
    db: AsyncSession, student_id: uuid.UUID, course_id: uuid.UUID
) -> Enrollment | None:
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
        )
    )
    return result.scalar_one_or_none()


async def list_for_student(
    db: AsyncSession, student_id: uuid.UUID, *, limit: int, offset: int
) -> list[Enrollment]:
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .options(selectinload(Enrollment.course))
        .order_by(Enrollment.enrolled_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def create(
    db: AsyncSession, *, student_id: uuid.UUID, course_id: uuid.UUID
) -> Enrollment:
    enrollment = Enrollment(student_id=student_id, course_id=course_id)
    db.add(enrollment)
    await db.flush()
    return enrollment
