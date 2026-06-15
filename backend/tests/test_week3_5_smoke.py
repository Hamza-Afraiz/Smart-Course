"""Smoke tests for Weeks 3–5 paths (outbox, search, RAG ask)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.course import Course, CourseStatus
from app.models.outbox import OutboxEvent
from app.services.rag_service import answer_stream
from tests.conftest import seed_lesson_chunks


async def _create_draft_with_text_lesson(
    client: AsyncClient, headers: dict[str, str], *, content: str
) -> dict:
    course = (
        await client.post(
            "/api/v1/courses",
            headers=headers,
            json={"title": "Smoke test course"},
        )
    ).json()
    mod = (
        await client.post(
            f"/api/v1/courses/{course['id']}/modules",
            headers=headers,
            json={"title": "Module 1", "order_index": 0},
        )
    ).json()
    lesson = (
        await client.post(
            f"/api/v1/courses/{course['id']}/modules/{mod['id']}/lessons",
            headers=headers,
            json={
                "title": "Intro",
                "order_index": 0,
                "content_type": "text",
                "content_text": content,
            },
        )
    ).json()
    course["_lesson_ids"] = [lesson["id"]]
    return course


@pytest.fixture
def mock_embed(monkeypatch):
    async def fake_embed(texts: list[str]) -> list[list[float]]:
        from app.models.lesson_chunk import EMBEDDING_DIM

        return [[0.0] * EMBEDDING_DIM for _ in texts]

    monkeypatch.setattr(
        "app.services.search_service.embedding_service.embed",
        fake_embed,
    )
    monkeypatch.setattr(
        "app.services.rag_service.embedding_service.embed",
        fake_embed,
    )


@pytest.fixture
def mock_llm(monkeypatch):
    async def fake_stream_chat(
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        yield "Raft is a consensus algorithm used in distributed systems."

    import app.services.llm_service as llm_mod

    monkeypatch.setattr(llm_mod, "stream_chat", fake_stream_chat)


async def test_enrollment_creates_outbox_row(
    client, student_headers, instructor_headers, engine
):
    course = await _create_draft_with_text_lesson(
        client,
        instructor_headers,
        content="Outbox smoke lesson body.",
    )
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        row = (
            await db.execute(select(Course).where(Course.id == uuid.UUID(course["id"])))
        ).scalar_one()
        row.status = CourseStatus.published
        await db.commit()

    resp = await client.post(
        f"/api/v1/courses/{course['id']}/enroll",
        headers=student_headers,
    )
    assert resp.status_code == 201, resp.text

    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "user.enrolled")
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_key.startswith("enrollment-")


async def test_semantic_search_finds_indexed_chunk(
    client, instructor_headers, engine, mock_embed
):
    text = "Gatekeepers guard the land in this fantasy story."
    course = await _create_draft_with_text_lesson(
        client, instructor_headers, content=text
    )
    await seed_lesson_chunks(
        engine,
        course_id=uuid.UUID(course["id"]),
        lesson_id=uuid.UUID(course["_lesson_ids"][0]),
        texts=[text],
    )

    resp = await client.post(
        "/api/v1/search/semantic",
        headers=instructor_headers,
        json={
            "query": "gatekeepers",
            "course_id": course["id"],
            "limit": 5,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["results"]
    assert "gatekeepers" in body["results"][0]["text"].lower()


async def test_pipeline_health_reports_healthy_outbox(
    client, instructor_headers, engine
):
    admin_email = f"admin-{uuid.uuid4().hex[:8]}@test.com"
    assert (
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": admin_email,
                "password": "secret123",
                "role": "admin",
            },
        )
    ).status_code == 201
    token = (
        await client.post(
            "/api/v1/auth/login",
            data={"username": admin_email, "password": "secret123"},
        )
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/admin/metrics/pipeline-health", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in ("healthy", "degraded", "critical")
    assert body["outbox"]["pending_count"] == 0


async def test_answer_stream_returns_grounded_tokens(
    client, instructor_headers, engine, mock_llm, mock_embed
):
    text = "Raft elects a leader for replicated logs."
    course = await _create_draft_with_text_lesson(
        client, instructor_headers, content=text
    )
    await seed_lesson_chunks(
        engine,
        course_id=uuid.UUID(course["id"]),
        lesson_id=uuid.UUID(course["_lesson_ids"][0]),
        texts=[text],
    )

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        tokens = [
            t
            async for t in answer_stream(
                db,
                question="What is Raft?",
                course_id=uuid.UUID(course["id"]),
            )
        ]
    assert any("Raft" in t for t in tokens)
