import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lesson import Lesson
from app.models.module import Module
from app.models.progress import Progress


async def create(
    db: AsyncSession, *, enrollment_id: uuid.UUID, lesson_id: uuid.UUID
) -> Progress:
    progress = Progress(enrollment_id=enrollment_id, lesson_id=lesson_id)
    db.add(progress)
    await db.flush()
    return progress


async def get_by_enrollment_and_lesson(
    db: AsyncSession, enrollment_id: uuid.UUID, lesson_id: uuid.UUID
) -> Progress | None:
    result = await db.execute(
        select(Progress).where(
            Progress.enrollment_id == enrollment_id,
            Progress.lesson_id == lesson_id,
        )
    )
    return result.scalar_one_or_none()


async def list_for_enrollment(
    db: AsyncSession, enrollment_id: uuid.UUID
) -> list[Progress]:
    result = await db.execute(
        select(Progress)
        .where(Progress.enrollment_id == enrollment_id)
        .order_by(Progress.completed_at.asc())
    )
    return list(result.scalars().all())


async def count_for_enrollment(db: AsyncSession, enrollment_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Progress)
        .where(Progress.enrollment_id == enrollment_id)
    )
    return int(result.scalar_one())


async def count_lessons_in_course(db: AsyncSession, course_id: uuid.UUID) -> int:
    """Total lessons across all modules of a course — used for completion math."""
    result = await db.execute(
        select(func.count())
        .select_from(Lesson)
        .join(Module, Lesson.module_id == Module.id)
        .where(Module.course_id == course_id)
    )
    return int(result.scalar_one())
