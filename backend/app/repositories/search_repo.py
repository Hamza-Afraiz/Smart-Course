"""pgvector retrieval — top-K nearest chunks by cosine similarity."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.lesson import Lesson
from app.models.lesson_chunk import LessonChunk
from app.models.module import Module


async def enrolled_course_ids(db: AsyncSession, student_id: uuid.UUID) -> list[uuid.UUID]:
    """Course ids the student is actively enrolled in (excludes dropped) —
    the access set for a student's global search."""
    result = await db.execute(
        select(Enrollment.course_id).where(
            Enrollment.student_id == student_id,
            Enrollment.status != EnrollmentStatus.dropped,
        )
    )
    return [row[0] for row in result.all()]


async def owned_course_ids(db: AsyncSession, instructor_id: uuid.UUID) -> list[uuid.UUID]:
    """Course ids owned by an instructor — their global-search access set."""
    result = await db.execute(
        select(Course.id).where(Course.instructor_id == instructor_id)
    )
    return [row[0] for row in result.all()]


async def search_chunks(
    db: AsyncSession,
    *,
    query_vector: list[float],
    course_id: uuid.UUID | None = None,
    course_ids: list[uuid.UUID] | None = None,
    limit: int,
) -> list[dict]:
    """Return the `limit` most similar chunks.

    Scope (apply at most one):
      - `course_id`  → a single course (course-detail search / RAG)
      - `course_ids` → a set of courses (global search across the user's
                       accessible courses). An empty list returns nothing.

    Uses pgvector's `<=>` cosine-distance operator (smaller = closer). The HNSW
    index on `lesson_chunks.embedding` makes this an ANN lookup — sub-millisecond
    even with millions of rows.
    """
    # Empty access set → no results (avoid a degenerate `IN ()` query)
    if course_ids is not None and len(course_ids) == 0:
        return []

    distance = LessonChunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(
            LessonChunk.lesson_id,
            Lesson.title.label("lesson_title"),
            LessonChunk.course_id,
            Course.title.label("course_title"),
            LessonChunk.chunk_index,
            LessonChunk.text,
            distance.label("distance"),
        )
        .join(Lesson, Lesson.id == LessonChunk.lesson_id)
        .join(Module, Module.id == Lesson.module_id)
        .join(Course, Course.id == Module.course_id)
        .order_by(distance)
        .limit(limit)
    )
    if course_id is not None:
        stmt = stmt.where(LessonChunk.course_id == course_id)
    elif course_ids is not None:
        stmt = stmt.where(LessonChunk.course_id.in_(course_ids))

    result = await db.execute(stmt)
    return [
        {
            "lesson_id": row.lesson_id,
            "lesson_title": row.lesson_title,
            "course_id": row.course_id,
            "course_title": row.course_title,
            "chunk_index": row.chunk_index,
            "text": row.text,
            # Embeddings are unit-normalised; cosine distance is in [0,2], with
            # 0 = identical. similarity = 1 - distance maps to [-1,1]; we clamp
            # to [0,1] for a UI-friendly score.
            "similarity": max(0.0, min(1.0, 1.0 - float(row.distance))),
        }
        for row in result.all()
    ]
