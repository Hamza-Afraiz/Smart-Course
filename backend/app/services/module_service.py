import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ModuleNotFoundError, OrderIndexConflictError
from app.models.module import Module
from app.models.user import User
from app.repositories import module_repo
from app.services import course_service


async def list_for_course(db: AsyncSession, course_id: uuid.UUID, viewer: User) -> list[Module]:
    # delegates the visibility check to course_service.get_for_view
    await course_service.get_for_view(db, course_id, viewer)
    return await module_repo.list_by_course(db, course_id)


async def get_for_modify(
    db: AsyncSession, course_id: uuid.UUID, module_id: uuid.UUID, actor: User
) -> Module:
    # confirms actor owns the course AND the module belongs to that course
    await course_service.get_for_modify(db, course_id, actor)
    module = await module_repo.get_by_id(db, module_id)
    if module is None or module.course_id != course_id:
        raise ModuleNotFoundError()
    return module


async def get_for_view(
    db: AsyncSession, course_id: uuid.UUID, module_id: uuid.UUID, viewer: User
) -> Module:
    # confirms the course is viewable AND the module belongs to that course
    await course_service.get_for_view(db, course_id, viewer)
    module = await module_repo.get_by_id(db, module_id)
    if module is None or module.course_id != course_id:
        raise ModuleNotFoundError()
    return module


async def create(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    actor: User,
    title: str,
    order_index: int,
) -> Module:
    await course_service.get_for_modify(db, course_id, actor)
    try:
        return await module_repo.create(
            db, course_id=course_id, title=title, order_index=order_index
        )
    except IntegrityError:
        # uq_module_course_order — another module already at this order_index
        await db.rollback()
        raise OrderIndexConflictError(
            f"A module at order_index={order_index} already exists in this course"
        )
