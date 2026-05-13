import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseStatus


async def get_by_id(db: AsyncSession, course_id: uuid.UUID) -> Course | None:
    result = await db.execute(select(Course).where(Course.id == course_id))
    return result.scalar_one_or_none()


async def list_published(db: AsyncSession, *, limit: int, offset: int) -> list[Course]:
    result = await db.execute(
        select(Course)
        .where(Course.status == CourseStatus.published)
        .order_by(Course.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def create(
    db: AsyncSession,
    *,
    title: str,
    description: str | None,
    instructor_id: uuid.UUID,
    max_students: int | None,
) -> Course:
    course = Course(
        title=title,
        description=description,
        instructor_id=instructor_id,
        max_students=max_students,
    )
    db.add(course)
    await db.flush()
    return course
