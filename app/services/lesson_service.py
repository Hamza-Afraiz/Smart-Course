import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import OrderIndexConflictError
from app.models.lesson import ContentType, Lesson
from app.models.user import User
from app.repositories import lesson_repo
from app.services import module_service


async def create(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    actor: User,
    title: str,
    order_index: int,
    content_type: ContentType | None,
    content_url: str | None,
    duration_seconds: int | None,
) -> Lesson:
    # ownership + module-belongs-to-course check in one call
    await module_service.get_for_modify(db, course_id, module_id, actor)
    try:
        return await lesson_repo.create(
            db,
            module_id=module_id,
            title=title,
            order_index=order_index,
            content_type=content_type,
            content_url=content_url,
            duration_seconds=duration_seconds,
        )
    except IntegrityError:
        await db.rollback()
        raise OrderIndexConflictError(
            f"A lesson at order_index={order_index} already exists in this module"
        )
