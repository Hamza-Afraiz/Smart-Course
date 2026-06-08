import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import OrderIndexConflictError
from app.models.lesson import ContentType, Lesson
from app.models.user import User
from app.repositories import lesson_repo
from app.services import module_service


async def list_for_module(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    viewer: User,
) -> list[Lesson]:
    # visibility + module-belongs-to-course check in one call
    await module_service.get_for_view(db, course_id, module_id, viewer)
    return await lesson_repo.list_by_module(db, module_id)


def effective_source(lesson: Lesson) -> tuple[str, str] | None:
    """Resolve a video/pdf lesson's content source.

    An uploaded file (storage_key) wins over a pasted URL. Returns
    ("storage", key) | ("url", url) | None. Used by both the extraction
    pipeline (download for Whisper/pypdf) and the source-cache key.
    """
    if lesson.storage_key:
        return ("storage", lesson.storage_key)
    if lesson.content_url:
        return ("url", lesson.content_url)
    return None


def source_fingerprint(lesson: Lesson) -> str | None:
    """A stable string identifying the current source, for cache invalidation."""
    src = effective_source(lesson)
    if src is None:
        return None
    kind, ref = src
    return f"{kind}:{ref}"


def playback_url(lesson: Lesson) -> str | None:
    """URL the browser uses to view the lesson media: a presigned GET when the
    file is in our object store, else the external content_url."""
    if lesson.storage_key:
        from app.services import storage_service

        return storage_service.presign_get(lesson.storage_key)
    return lesson.content_url


def to_response(lesson: Lesson):
    """Build a LessonResponse with the resolved playback_url filled in."""
    from app.schemas.lesson import LessonResponse

    resp = LessonResponse.model_validate(lesson)
    resp.playback_url = playback_url(lesson)
    return resp


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
    content_text: str | None,
    storage_key: str | None,
    mime_type: str | None,
    file_size: int | None,
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
            content_text=content_text,
            storage_key=storage_key,
            mime_type=mime_type,
            file_size=file_size,
            duration_seconds=duration_seconds,
        )
    except IntegrityError:
        await db.rollback()
        raise OrderIndexConflictError(
            f"A lesson at order_index={order_index} already exists in this module"
        )
