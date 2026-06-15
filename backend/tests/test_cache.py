import uuid

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import cache
from app.config import settings
from app.models.course import Course
from tests.course_helpers import make_published_course_direct


@pytest_asyncio.fixture
async def make_published_course(client, engine, instructor_headers):
    """Override the conftest fixture with a Temporal-free direct publish."""
    async def _factory(*, title: str = "Course", max_students: int | None = None):
        return await make_published_course_direct(
            client, engine, instructor_headers, title=title, max_students=max_students
        )

    return _factory


async def _redis_or_skip() -> None:
    r = aioredis.from_url(settings.redis_url, socket_connect_timeout=0.5)
    try:
        await r.ping()
    except Exception:
        pytest.skip("redis not available")
    await r.flushdb()
    await r.aclose()


@pytest.fixture
def cache_on(monkeypatch):
    """Enable the best-effort cache for one test + reset the circuit breaker.

    pytest-asyncio gives each test its own event loop, but the cache client is a
    module singleton bound to the loop it was created on. Reset it so each test
    builds a fresh client on its own loop (a non-issue in prod's single loop).
    """
    monkeypatch.setattr(settings, "cache_enabled", True)
    cache._disabled_until = 0.0
    cache._client = None
    yield
    cache._client = None


async def _set_title_in_db(engine, course_id: str, title: str) -> None:
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as s:
        await s.execute(
            sa_update(Course).where(Course.id == uuid.UUID(course_id)).values(title=title)
        )
        await s.commit()


async def test_course_detail_is_cached_then_invalidated(
    client, instructor_headers, student_headers, make_published_course, engine, cache_on
):
    await _redis_or_skip()
    course = await make_published_course(title="Old")

    g1 = await client.get(f"/api/v1/courses/{course['id']}", headers=student_headers)
    assert g1.status_code == 200
    assert g1.json()["title"] == "Old"

    # mutate the row directly, bypassing the API → cache is NOT invalidated
    await _set_title_in_db(engine, course["id"], "DirectDB")
    g2 = await client.get(f"/api/v1/courses/{course['id']}", headers=student_headers)
    assert g2.json()["title"] == "Old"  # stale read proves the cache served it

    # update through the API → invalidation fires
    p = await client.patch(
        f"/api/v1/courses/{course['id']}",
        headers=instructor_headers,
        json={"title": "ViaAPI"},
    )
    assert p.status_code == 200
    g3 = await client.get(f"/api/v1/courses/{course['id']}", headers=student_headers)
    assert g3.json()["title"] == "ViaAPI"  # fresh read proves invalidation worked


async def test_archive_drops_course_from_cached_catalog(
    client, instructor_headers, student_headers, make_published_course, cache_on
):
    await _redis_or_skip()
    course = await make_published_course(title="Catalog Course")

    c1 = await client.get("/api/v1/courses", headers=student_headers)
    assert any(c["id"] == course["id"] for c in c1.json())

    d = await client.delete(
        f"/api/v1/courses/{course['id']}", headers=instructor_headers
    )
    assert d.status_code == 200
    c2 = await client.get("/api/v1/courses", headers=student_headers)
    assert not any(c["id"] == course["id"] for c in c2.json())


async def test_reads_work_with_cache_disabled(
    client, student_headers, make_published_course
):
    """Default under test: cache off → reads still serve correctly from Postgres."""
    course = await make_published_course(title="NoCache")
    g = await client.get(f"/api/v1/courses/{course['id']}", headers=student_headers)
    assert g.status_code == 200
    assert g.json()["title"] == "NoCache"
