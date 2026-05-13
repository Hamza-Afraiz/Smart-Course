import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module import Module


async def get_by_id(db: AsyncSession, module_id: uuid.UUID) -> Module | None:
    result = await db.execute(select(Module).where(Module.id == module_id))
    return result.scalar_one_or_none()


async def list_by_course(db: AsyncSession, course_id: uuid.UUID) -> list[Module]:
    result = await db.execute(
        select(Module)
        .where(Module.course_id == course_id)
        .order_by(Module.order_index.asc())
    )
    return list(result.scalars().all())


async def create(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    title: str,
    order_index: int,
) -> Module:
    module = Module(course_id=course_id, title=title, order_index=order_index)
    db.add(module)
    await db.flush()
    return module
