"""Tier 2 — certificates, re-index, traceparent, welcome email."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.certificate import Certificate
from app.models.course import Course, CourseStatus
from app.models.enrollment import Enrollment
from app.models.outbox import OutboxEvent
from app.models.user import UserRole
from app.observability.propagation import inject_traceparent
from app.repositories import user_repo
from app.services import event_service
from app.services.auth_service import _hash_password


# ── Certificates ──────────────────────────────────────────────────────────────


async def test_certificate_issued_when_enrollment_completes(
    client, student_headers, make_published_course
):
    course = await make_published_course(title="Cert Course")
    lesson1, lesson2 = course["_lesson_ids"]
    enroll = (
        await client.post(
            f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
        )
    ).json()

    await client.post(
        f"/api/v1/enrollments/{enroll['id']}/progress/{lesson1}",
        headers=student_headers,
    )
    empty = await client.get("/api/v1/certificates/me", headers=student_headers)
    assert empty.status_code == 200
    assert empty.json() == []

    await client.post(
        f"/api/v1/enrollments/{enroll['id']}/progress/{lesson2}",
        headers=student_headers,
    )

    resp = await client.get("/api/v1/certificates/me", headers=student_headers)
    assert resp.status_code == 200, resp.text
    certs = resp.json()
    assert len(certs) == 1
    assert certs[0]["course_id"] == course["id"]
    assert certs[0]["enrollment_id"] == enroll["id"]
    assert certs[0]["course_title"] == "Cert Course"
    assert certs[0]["issued_at"]


async def test_certificate_idempotent_one_per_enrollment(
    client, student_headers, make_published_course, engine
):
    course = await make_published_course()
    lesson1, lesson2 = course["_lesson_ids"]
    enroll = (
        await client.post(
            f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
        )
    ).json()
    for lid in (lesson1, lesson2):
        await client.post(
            f"/api/v1/enrollments/{enroll['id']}/progress/{lid}",
            headers=student_headers,
        )
    # Idempotent re-complete
    await client.post(
        f"/api/v1/enrollments/{enroll['id']}/progress/{lesson1}",
        headers=student_headers,
    )

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        count = (
            await db.execute(
                select(func.count())
                .select_from(Certificate)
                .where(Certificate.enrollment_id == uuid.UUID(enroll["id"]))
            )
        ).scalar_one()
    assert count == 1


async def test_certificates_me_student_only(
    client, instructor_headers, student_headers, make_published_course
):
    await make_published_course()
    resp = await client.get("/api/v1/certificates/me", headers=instructor_headers)
    assert resp.status_code == 403


# ── Re-index ──────────────────────────────────────────────────────────────────


async def test_reindex_published_course_returns_202(
    client, instructor_headers, make_published_course, monkeypatch
):
    course = await make_published_course()
    calls: list[tuple[str, str | None]] = []

    def fake_delay(course_id: str, traceparent: str | None = None) -> None:
        calls.append((course_id, traceparent))

    monkeypatch.setattr(
        "app.tasks.reindex_course.reindex_course.delay",
        fake_delay,
    )

    resp = await client.post(
        f"/api/v1/courses/{course['id']}/reindex",
        headers=instructor_headers,
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["course_id"] == course["id"]
    assert body["task"] == "tasks.reindex_course"
    assert len(calls) == 1
    assert calls[0][0] == course["id"]


async def test_reindex_draft_course_returns_409(
    client, instructor_headers, monkeypatch
):
    monkeypatch.setattr(
        "app.tasks.reindex_course.reindex_course.delay",
        MagicMock(),
    )
    resp = await client.post(
        "/api/v1/courses",
        headers=instructor_headers,
        json={"title": "draft only"},
    )
    course_id = resp.json()["id"]
    resp = await client.post(
        f"/api/v1/courses/{course_id}/reindex",
        headers=instructor_headers,
    )
    assert resp.status_code == 409


async def test_reindex_non_owner_returns_403(
    client, instructor_headers, other_instructor_headers, make_published_course, monkeypatch
):
    monkeypatch.setattr(
        "app.tasks.reindex_course.reindex_course.delay",
        MagicMock(),
    )
    course = await make_published_course()
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/reindex",
        headers=other_instructor_headers,
    )
    assert resp.status_code == 403


async def test_reindex_task_calls_indexing_service(
    monkeypatch, make_published_course, client, instructor_headers
):
    course = await make_published_course()
    indexed: list[str] = []

    async def fake_index(db, course_id: uuid.UUID) -> int:
        indexed.append(str(course_id))
        return 2

    monkeypatch.setattr(
        "app.services.content_indexing_service.index_course_lessons",
        fake_index,
    )

    from app.tasks.reindex_course import _reindex

    await _reindex(course["id"], traceparent=None)
    assert indexed == [course["id"]]


# ── traceparent propagation ───────────────────────────────────────────────────


@pytest.fixture
def otel_tracer():
    trace.set_tracer_provider(TracerProvider())
    return trace.get_tracer("tier2-test")


async def test_event_emit_stores_traceparent_in_outbox(engine, otel_tracer):
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    expected: str | None = None

    async with SessionLocal() as db:
        with otel_tracer.start_as_current_span("test-emit"):
            expected = inject_traceparent()
            assert expected is not None
            await event_service.emit(
                db,
                event_type="user.enrolled",
                event_key="enrollment-test-1",
                payload={"enrollment_id": "x"},
            )
            await db.commit()

    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(OutboxEvent).where(OutboxEvent.event_key == "enrollment-test-1")
            )
        ).scalar_one()
    assert row.traceparent == expected
    assert row.traceparent.startswith("00-")


async def test_enrollment_outbox_row_has_traceparent_when_span_active(
    client, student_headers, instructor_headers, engine, otel_tracer
):
    from tests.test_week3_5_smoke import _create_draft_with_text_lesson

    course = await _create_draft_with_text_lesson(
        client, instructor_headers, content="Traceparent lesson."
    )
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        row = (
            await db.execute(select(Course).where(Course.id == uuid.UUID(course["id"])))
        ).scalar_one()
        row.status = CourseStatus.published
        await db.commit()

    with otel_tracer.start_as_current_span("enroll-http"):
        expected = inject_traceparent()
        resp = await client.post(
            f"/api/v1/courses/{course['id']}/enroll",
            headers=student_headers,
        )
    assert resp.status_code == 201, resp.text

    async with SessionLocal() as db:
        outbox = (
            await db.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "user.enrolled")
            )
        ).scalar_one()
    # FastAPI test client may or may not attach OTel context — if absent, traceparent is None.
    if expected:
        assert outbox.traceparent == expected


# ── Welcome email ─────────────────────────────────────────────────────────────


async def test_welcome_email_task_sends_smtp(engine, monkeypatch):
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        instructor = await user_repo.create(
            db,
            email="inst@welcome.test",
            hashed_password=_hash_password("secret123"),
            full_name="Inst",
            role=UserRole.instructor,
        )
        from app.models.course import Course as CourseModel

        course = CourseModel(
            title="Welcome 101",
            instructor_id=instructor.id,
            status=CourseStatus.published,
        )
        db.add(course)
        await db.flush()
        student = await user_repo.create(
            db,
            email="student@welcome.test",
            hashed_password=_hash_password("secret123"),
            full_name="Learner",
            role=UserRole.student,
        )
        enrollment = Enrollment(
            student_id=student.id,
            course_id=course.id,
        )
        db.add(enrollment)
        await db.commit()
        enrollment_id = str(enrollment.id)

    sent: list[dict[str, str]] = []

    async def fake_send(*, to: str, subject: str, body: str) -> None:
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("app.tasks.welcome_email.send_email", fake_send)

    from app.tasks.welcome_email import _send

    await _send(enrollment_id, traceparent=None)

    assert len(sent) == 1
    assert sent[0]["to"] == "student@welcome.test"
    assert "Welcome 101" in sent[0]["subject"]
    assert "Welcome 101" in sent[0]["body"]


async def test_welcome_email_skips_missing_enrollment(engine, monkeypatch):
    sent: list[dict[str, str]] = []

    async def fake_send(*, to: str, subject: str, body: str) -> None:
        sent.append({"to": to})

    monkeypatch.setattr("app.tasks.welcome_email.send_email", fake_send)

    from app.tasks.welcome_email import _send

    await _send(str(uuid.uuid4()), traceparent=None)
    assert sent == []
