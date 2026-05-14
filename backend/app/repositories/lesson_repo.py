import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.lesson import ContentType, Lesson
from app.models.module import Module


async def get_by_id(db: AsyncSession, lesson_id: uuid.UUID) -> Lesson | None:
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    return result.scalar_one_or_none()


async def get_with_module(db: AsyncSession, lesson_id: uuid.UUID) -> Lesson | None:
    """Fetch a lesson with its parent module eagerly loaded.

    Used when callers need lesson.module.course_id without triggering a
    sync lazy load on the async session.
    """
    result = await db.execute(
        select(Lesson)
        .options(joinedload(Lesson.module))
        .where(Lesson.id == lesson_id)
    )
    return result.scalar_one_or_none()


async def get_course_id(db: AsyncSession, lesson_id: uuid.UUID) -> uuid.UUID | None:
    """Return the course_id of the lesson's parent module, or None if not found."""
    result = await db.execute(
        select(Module.course_id)
        .join(Lesson, Lesson.module_id == Module.id)
        .where(Lesson.id == lesson_id)
    )
    return result.scalar_one_or_none()


async def list_by_module(db: AsyncSession, module_id: uuid.UUID) -> list[Lesson]:
    result = await db.execute(
        select(Lesson)
        .where(Lesson.module_id == module_id)
        .order_by(Lesson.order_index.asc())
    )
    return list(result.scalars().all())


async def create(
    db: AsyncSession,
    *,
    module_id: uuid.UUID,
    title: str,
    order_index: int,
    content_type: ContentType | None,
    content_url: str | None,
    duration_seconds: int | None,
) -> Lesson:
    lesson = Lesson(
        module_id=module_id,
        title=title,
        order_index=order_index,
        content_type=content_type,
        content_url=content_url,
        duration_seconds=duration_seconds,
    )
    db.add(lesson)
    await db.flush()
    return lesson
