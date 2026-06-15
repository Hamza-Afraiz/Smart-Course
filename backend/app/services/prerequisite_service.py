import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidPrerequisiteError, PrerequisiteCycleError
from app.models.course import Course
from app.models.user import User
from app.repositories import course_repo, prerequisite_repo
from app.services import course_service


async def add_prerequisite(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    prerequisite_id: uuid.UUID,
    actor: User,
) -> list[Course]:
    course = await course_service.get_for_modify(db, course_id, actor)

    if prerequisite_id == course.id:
        raise InvalidPrerequisiteError("A course cannot be its own prerequisite")

    prereq = await course_repo.get_by_id(db, prerequisite_id)
    if prereq is None:
        raise InvalidPrerequisiteError("Prerequisite course does not exist")

    if await prerequisite_repo.would_create_cycle(
        db, course_id=course_id, prerequisite_id=prerequisite_id
    ):
        raise PrerequisiteCycleError(
            f"'{prereq.title}' already requires '{course.title}' "
            "(directly or transitively) — adding this would create a cycle"
        )

    await prerequisite_repo.add(
        db, course_id=course_id, prerequisite_id=prerequisite_id
    )
    return await prerequisite_repo.list_prerequisites(db, course_id)


async def remove_prerequisite(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    prerequisite_id: uuid.UUID,
    actor: User,
) -> None:
    await course_service.get_for_modify(db, course_id, actor)
    await prerequisite_repo.remove(
        db, course_id=course_id, prerequisite_id=prerequisite_id
    )


async def list_prerequisites(
    db: AsyncSession, *, course_id: uuid.UUID, viewer: User
) -> list[Course]:
    await course_service.get_for_view(db, course_id, viewer)
    return await prerequisite_repo.list_prerequisites(db, course_id)
