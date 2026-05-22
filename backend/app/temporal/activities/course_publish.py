"""Temporal activities for course publishing (DB side effects).

Registered on the worker. Each activity opens its own AsyncSession and commits.
Tests may override the session factory via configure_activity_session_factory().
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.config import settings
from app.models.course import Course, CourseStatus
from app.models.lesson import Lesson
from app.models.module import Module

_activity_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_activity_session_factory(
    factory: async_sessionmaker[AsyncSession] | None,
) -> None:
    """Override DB session factory (used by tests). Pass None to reset to default."""
    global _activity_session_factory
    _activity_session_factory = factory


def _session_factory() -> async_sessionmaker[AsyncSession]:
    if _activity_session_factory is None:
        from app.database import AsyncSessionLocal

        return AsyncSessionLocal
    return _activity_session_factory


@asynccontextmanager
async def _session_scope() -> AsyncIterator[AsyncSession]:
    factory = _session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _fail_if_test_injected(step: str) -> None:
    target = os.environ.get("TEST_PUBLISH_FAIL_STEP", "")
    if target == step:
        raise ApplicationError(f"injected failure at {step}", non_retryable=True)


async def _count_lessons(session: AsyncSession, course_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Lesson)
        .join(Module, Lesson.module_id == Module.id)
        .where(Module.course_id == course_id)
    )
    return int(result.scalar_one())


@activity.defn
async def validate_course_activity(course_id: str, instructor_id: str) -> None:
    cid = uuid.UUID(course_id)
    iid = uuid.UUID(instructor_id)
    async with _session_scope() as session:
        result = await session.execute(select(Course).where(Course.id == cid))
        course = result.scalar_one_or_none()
        if course is None:
            raise ApplicationError("Course not found", non_retryable=True)
        if course.status != CourseStatus.draft:
            raise ApplicationError(
                f"Course must be draft, got {course.status.value}", non_retryable=True
            )
        if course.instructor_id != iid:
            raise ApplicationError("Instructor does not own this course", non_retryable=True)
        n = await _count_lessons(session, cid)
        if n < 1:
            raise ApplicationError(
                "Course must have at least one module with one lesson", non_retryable=True
            )


@activity.defn
async def process_lessons_activity(course_id: str, idempotency_key: str) -> None:
    _ = idempotency_key  # reserved for future idempotency table / Week 4 pipeline
    _fail_if_test_injected("process")
    cid = uuid.UUID(course_id)
    async with _session_scope() as session:
        result = await session.execute(select(Course).where(Course.id == cid))
        course = result.scalar_one_or_none()
        if course is None:
            raise ApplicationError("Course not found", non_retryable=True)
        course.processed_at = datetime.now(timezone.utc)
        await session.flush()


@activity.defn
async def mark_published_activity(course_id: str, idempotency_key: str) -> None:
    _ = idempotency_key
    _fail_if_test_injected("mark")
    cid = uuid.UUID(course_id)
    async with _session_scope() as session:
        result = await session.execute(select(Course).where(Course.id == cid))
        course = result.scalar_one_or_none()
        if course is None:
            raise ApplicationError("Course not found", non_retryable=True)
        if course.status == CourseStatus.published:
            return
        if course.status != CourseStatus.draft:
            raise ApplicationError(
                f"Cannot publish from status {course.status.value}", non_retryable=True
            )
        course.status = CourseStatus.published
        await session.flush()


@activity.defn
async def emit_course_published_activity(course_id: str, run_id: str) -> None:
    """Announce `course.published` by publishing directly to Kafka.

    This is one of the two places we bypass the outbox table — Temporal's
    workflow history is the durability layer here. If this activity fails,
    Temporal retries it with the same idempotency_key; if it succeeds twice
    (rare network edge), consumer-side dedupe on `event_key` absorbs it.

    Per the architecture rule in docs/QA.md:
      - event from a normal DB transaction → outbox-then-relay
      - event from inside a Temporal workflow → activity-direct-to-Kafka
    """
    idempotency_key = f"publish-{course_id}-{run_id}"
    payload = json.dumps(
        {
            "course_id": course_id,
            "workflow_run_id": run_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        acks="all",
        enable_idempotence=True,
        client_id="temporal-course-publish",
    )
    await producer.start()
    try:
        await producer.send_and_wait(
            topic="events.course.published",
            key=idempotency_key.encode(),
            value=payload,
            headers=[
                ("idempotency_key", idempotency_key.encode()),
                ("event_type", b"course.published"),
                ("source", b"temporal-workflow"),
            ],
        )
    finally:
        await producer.stop()


@activity.defn
async def delete_processed_data_activity(course_id: str) -> None:
    cid = uuid.UUID(course_id)
    async with _session_scope() as session:
        result = await session.execute(select(Course).where(Course.id == cid))
        course = result.scalar_one_or_none()
        if course is None:
            return
        course.processed_at = None
        await session.flush()


@activity.defn
async def revert_to_draft_activity(course_id: str) -> None:
    cid = uuid.UUID(course_id)
    async with _session_scope() as session:
        result = await session.execute(select(Course).where(Course.id == cid))
        course = result.scalar_one_or_none()
        if course is None:
            return
        if course.status == CourseStatus.published:
            course.status = CourseStatus.draft
        await session.flush()
