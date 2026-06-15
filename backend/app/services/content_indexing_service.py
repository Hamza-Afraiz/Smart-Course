"""Extract → chunk → embed pipeline shared by publish workflow and re-index."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.lesson import ContentType, Lesson
from app.models.lesson_chunk import LessonChunk
from app.models.module import Module
from app.services.chunking_service import chunk_text
from app.services.embedding_service import embed

logger = logging.getLogger(__name__)


async def _lesson_text(lesson: Lesson) -> str | None:
    from app.services import extraction_service, lesson_service, storage_service

    if lesson.content_type == ContentType.text:
        return lesson.content_text or None

    src = lesson_service.effective_source(lesson)
    if src is None:
        return None
    fingerprint = lesson_service.source_fingerprint(lesson)

    if lesson.cached_text and lesson.cached_text_source == fingerprint:
        logger.info("extraction cache hit for lesson=%s", lesson.id)
        return lesson.cached_text

    kind, ref = src
    text: str | None = None

    if lesson.content_type == ContentType.video:
        if kind == "url":
            text = await extraction_service.extract_video_text(ref)
        else:
            data = await asyncio.to_thread(storage_service.get_bytes, ref)
            text = await extraction_service.transcribe_bytes(data)
    elif lesson.content_type == ContentType.pdf:
        if kind == "url":
            text = await extraction_service.extract_pdf(ref)
        else:
            data = await asyncio.to_thread(storage_service.get_bytes, ref)
            text = await extraction_service.extract_pdf_bytes(data)

    if text:
        lesson.cached_text = text
        lesson.cached_text_source = fingerprint

    return text


async def index_course_lessons(db: AsyncSession, course_id: uuid.UUID) -> int:
    """Re-chunk and embed all lessons for a course. Returns chunk count."""
    course = (
        await db.execute(select(Course).where(Course.id == course_id))
    ).scalar_one_or_none()
    if course is None:
        raise ValueError("Course not found")

    lessons = (
        await db.execute(
            select(Lesson)
            .join(Module, Lesson.module_id == Module.id)
            .where(Module.course_id == course_id)
        )
    ).scalars().all()

    await db.execute(delete(LessonChunk).where(LessonChunk.course_id == course_id))

    total_chunks = 0
    for lesson in lessons:
        source = await _lesson_text(lesson)
        if not source:
            continue
        chunks = chunk_text(source)
        if not chunks:
            continue
        vectors = await embed([c.text for c in chunks])
        for idx, (c, v) in enumerate(zip(chunks, vectors)):
            db.add(
                LessonChunk(
                    lesson_id=lesson.id,
                    course_id=course_id,
                    chunk_index=idx,
                    text=c.text,
                    token_count=c.token_count,
                    embedding=v,
                )
            )
            total_chunks += 1

    course.processed_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info(
        "index_course_lessons: course=%s lessons=%d chunks=%d",
        course_id,
        len(lessons),
        total_chunks,
    )
    return total_chunks
