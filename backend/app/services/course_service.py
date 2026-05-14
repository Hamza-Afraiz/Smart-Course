import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    CourseNotFoundError,
    ForbiddenError,
    InvalidStatusTransitionError,
)
from app.models.course import Course, CourseStatus
from app.models.user import User, UserRole
from app.repositories import course_repo

# allowed status transitions — anything else raises InvalidStatusTransitionError
_ALLOWED_TRANSITIONS: dict[CourseStatus, set[CourseStatus]] = {
    CourseStatus.draft: {CourseStatus.archived},
    CourseStatus.published: {CourseStatus.archived},
    CourseStatus.archived: set(),
}


def _can_modify(user: User, course: Course) -> bool:
    return user.role == UserRole.admin or course.instructor_id == user.id


async def get_for_view(db: AsyncSession, course_id: uuid.UUID, viewer: User) -> Course:
    """
    Fetch a course for read.
    - Published courses are visible to everyone.
    - Draft/archived are only visible to the owner or an admin.
    """
    course = await course_repo.get_by_id(db, course_id)
    if course is None:
        raise CourseNotFoundError()

    if course.status != CourseStatus.published and not _can_modify(viewer, course):
        # don't leak that the course exists
        raise CourseNotFoundError()
    return course


async def get_for_modify(db: AsyncSession, course_id: uuid.UUID, actor: User) -> Course:
    course = await course_repo.get_by_id(db, course_id)
    if course is None:
        raise CourseNotFoundError()
    if not _can_modify(actor, course):
        raise ForbiddenError("Only the course owner or an admin can modify this course")
    return course


async def list_published(db: AsyncSession, *, limit: int, offset: int) -> list[Course]:
    return await course_repo.list_published(db, limit=limit, offset=offset)


async def list_owned(
    db: AsyncSession, *, instructor: User, limit: int, offset: int
) -> list[Course]:
    """Every course this instructor owns — draft, published, and archived."""
    return await course_repo.list_by_instructor(
        db, instructor.id, limit=limit, offset=offset
    )


async def create(
    db: AsyncSession,
    *,
    instructor: User,
    title: str,
    description: str | None,
    max_students: int | None,
) -> Course:
    return await course_repo.create(
        db,
        title=title,
        description=description,
        instructor_id=instructor.id,
        max_students=max_students,
    )


async def update(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    actor: User,
    title: str | None,
    description: str | None,
    max_students: int | None,
    status: CourseStatus | None,
) -> Course:
    course = await get_for_modify(db, course_id, actor)

    if status is not None and status != course.status:
        if status == CourseStatus.published:
            raise InvalidStatusTransitionError(
                "Use POST /api/v1/courses/{course_id}/publish to publish a course"
            )
        if status not in _ALLOWED_TRANSITIONS[course.status]:
            raise InvalidStatusTransitionError(
                f"Cannot transition from {course.status.value} to {status.value}"
            )
        course.status = status

    if title is not None:
        course.title = title
    if description is not None:
        course.description = description
    if max_students is not None:
        course.max_students = max_students

    await db.flush()
    # onupdate=func.now() on updated_at expires the attr after flush — refresh inside
    # the async context so Pydantic serialization doesn't trigger a sync lazy-load
    await db.refresh(course)
    return course


async def soft_delete(db: AsyncSession, *, course_id: uuid.UUID, actor: User) -> Course:
    """Archive instead of delete — preserves enrollment/progress FK integrity."""
    course = await get_for_modify(db, course_id, actor)
    course.status = CourseStatus.archived
    await db.flush()
    await db.refresh(course)
    return course
