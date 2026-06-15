"""Tests for POST /api/v1/assistant/generate (instructor summary / quiz)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import User

from app.services.rag_service import (
    _QUIZ_QUESTION_BLOCK,
    _QUIZ_SYSTEM,
    build_generation_prompts,
    generate_stream,
)
from tests.conftest import seed_lesson_chunks


async def _create_draft_with_text_lesson(
    client: AsyncClient, headers: dict[str, str], *, content: str
) -> dict:
    course = (
        await client.post(
            "/api/v1/courses",
            headers=headers,
            json={"title": "Gen test course"},
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
    course["_module_id"] = mod["id"]
    course["_lesson_ids"] = [lesson["id"]]
    return course


async def _load_user(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one()


@pytest.fixture
def mock_llm(monkeypatch):
    """Stub Ollama — yields deterministic tokens; never hits the network."""

    async def fake_stream_chat(
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        if "multiple-choice quiz" in user:
            yield "### Question 1\n"
            yield "**Question:** What is Raft?\n"
            yield "**Correct answer:** B\n"
        else:
            yield "- Key point one\n"
            yield "- Key point two\n"

    import app.services.llm_service as llm_mod

    monkeypatch.setattr(llm_mod, "stream_chat", fake_stream_chat)


@pytest.fixture
def mock_embed(monkeypatch):
    """Avoid loading sentence-transformers during HTTP tests that hit retrieve()."""

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        from app.models.lesson_chunk import EMBEDDING_DIM

        return [[0.0] * EMBEDDING_DIM for _ in texts]

    monkeypatch.setattr(
        "app.services.rag_service.embedding_service.embed",
        fake_embed,
    )


# ── Prompt format (unit) ──────────────────────────────────────────────────────


def test_quiz_prompt_uses_strict_markdown_template():
    system, user, temp = build_generation_prompts(
        kind="quiz",
        scope="Intro",
        context="[Intro] Raft is a consensus algorithm.",
    )
    assert temp == 0.1
    assert system == _QUIZ_SYSTEM
    assert "Context from Intro" in user
    assert "### Question 1" in user
    assert "**Question:**" in user
    assert "**Correct answer:**" in user
    assert "**Explanation:**" in user
    assert "- A)" in user
    assert _QUIZ_QUESTION_BLOCK.format(n=1) in user
    assert "Do not add any text before the first question" in user


def test_summary_prompt_uses_bullet_summary_instructions():
    system, user, temp = build_generation_prompts(
        kind="summary",
        scope="this course",
        context="[Intro] Distributed systems basics.",
    )
    assert temp == 0.2
    assert "bullet" in system.lower() or "Summarize" in system
    assert "summary of the key points" in user
    assert "Distributed systems basics" in user


# ── HTTP — auth & ownership ───────────────────────────────────────────────────


async def test_student_cannot_generate_returns_403(
    client, student_headers, instructor_headers, engine, mock_llm, mock_embed
):
    course = await _create_draft_with_text_lesson(
        client,
        instructor_headers,
        content="Students should not call generate.",
    )
    await seed_lesson_chunks(
        engine,
        course_id=uuid.UUID(course["id"]),
        lesson_id=uuid.UUID(course["_lesson_ids"][0]),
        texts=["Students should not call generate."],
    )
    resp = await client.post(
        "/api/v1/assistant/generate",
        headers=student_headers,
        json={
            "course_id": course["id"],
            "kind": "summary",
            "lesson_id": None,
        },
    )
    assert resp.status_code == 403


async def test_non_owner_instructor_cannot_generate_returns_403(
    client, instructor_headers, other_instructor_headers, engine, mock_llm, mock_embed
):
    course = await _create_draft_with_text_lesson(
        client,
        instructor_headers,
        content="Ownership required.",
    )
    await seed_lesson_chunks(
        engine,
        course_id=uuid.UUID(course["id"]),
        lesson_id=uuid.UUID(course["_lesson_ids"][0]),
        texts=["Ownership required."],
    )
    resp = await client.post(
        "/api/v1/assistant/generate",
        headers=other_instructor_headers,
        json={"course_id": course["id"], "kind": "quiz"},
    )
    assert resp.status_code == 403


async def test_generate_unknown_course_returns_404(
    client, instructor_headers, mock_llm
):
    resp = await client.post(
        "/api/v1/assistant/generate",
        headers=instructor_headers,
        json={
            "course_id": str(uuid.uuid4()),
            "kind": "summary",
        },
    )
    assert resp.status_code == 404


# ── Service — streaming generation ─────────────────────────────────────────────


async def test_generate_stream_summary(
    client, instructor_headers, engine, mock_llm
):
    course = await _create_draft_with_text_lesson(
        client,
        instructor_headers,
        content="Consensus algorithms ensure agreement across nodes.",
    )
    await seed_lesson_chunks(
        engine,
        course_id=uuid.UUID(course["id"]),
        lesson_id=uuid.UUID(course["_lesson_ids"][0]),
        texts=["Consensus algorithms ensure agreement across nodes."],
    )
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        actor = await _load_user(db, "instructor@test.com")
        tokens = [
            t
            async for t in generate_stream(
                db,
                course_id=uuid.UUID(course["id"]),
                lesson_id=uuid.UUID(course["_lesson_ids"][0]),
                kind="summary",
                actor=actor,
            )
        ]
    assert any("Key point" in t for t in tokens)


async def test_generate_stream_quiz_uses_structured_markdown(
    client, instructor_headers, engine, mock_llm
):
    course = await _create_draft_with_text_lesson(
        client,
        instructor_headers,
        content="Raft elects a leader for log replication.",
    )
    await seed_lesson_chunks(
        engine,
        course_id=uuid.UUID(course["id"]),
        lesson_id=uuid.UUID(course["_lesson_ids"][0]),
        texts=["Raft elects a leader for log replication."],
    )
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        actor = await _load_user(db, "instructor@test.com")
        text = "".join(
            [
                t
                async for t in generate_stream(
                    db,
                    course_id=uuid.UUID(course["id"]),
                    lesson_id=uuid.UUID(course["_lesson_ids"][0]),
                    kind="quiz",
                    actor=actor,
                )
            ]
        )
    assert "### Question 1" in text
    assert "**Question:**" in text
    assert "**Correct answer:**" in text


async def test_generate_stream_without_chunks_returns_publish_hint(
    client, instructor_headers, engine, mock_llm
):
    course = await _create_draft_with_text_lesson(
        client,
        instructor_headers,
        content="Not indexed yet — no chunks seeded.",
    )
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        actor = await _load_user(db, "instructor@test.com")
        tokens = [
            t
            async for t in generate_stream(
                db,
                course_id=uuid.UUID(course["id"]),
                lesson_id=None,
                kind="summary",
                actor=actor,
            )
        ]
    text = "".join(tokens)
    assert "Publish the course first" in text
    assert "chunk" in text.lower()

