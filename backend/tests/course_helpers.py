import uuid

from httpx import AsyncClient
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.course import Course, CourseStatus


async def make_published_course_direct(
    client: AsyncClient,
    engine,
    instructor_headers: dict,
    *,
    title: str = "Course",
    max_students: int | None = None,
) -> dict:
    """Create a course + module + 2 lessons, then publish it by flipping status
    directly in the DB.

    Deliberately bypasses the Temporal publish workflow: that workflow runs the
    Week 4 chunk+embed pipeline (torch / sentence-transformers), which the
    prerequisite / cache / recommendation features don't depend on. The publish
    workflow itself is covered by tests/test_temporal_publish.py.
    """
    payload: dict = {"title": title}
    if max_students is not None:
        payload["max_students"] = max_students
    resp = await client.post("/api/v1/courses", headers=instructor_headers, json=payload)
    assert resp.status_code == 201, resp.text
    course = resp.json()

    mod = (
        await client.post(
            f"/api/v1/courses/{course['id']}/modules",
            headers=instructor_headers,
            json={"title": "m0", "order_index": 0},
        )
    ).json()

    lesson_ids: list[str] = []
    for i in range(2):
        les = await client.post(
            f"/api/v1/courses/{course['id']}/modules/{mod['id']}/lessons",
            headers=instructor_headers,
            json={"title": f"l{i}", "order_index": i},
        )
        assert les.status_code == 201, les.text
        lesson_ids.append(les.json()["id"])

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as s:
        await s.execute(
            sa_update(Course)
            .where(Course.id == uuid.UUID(course["id"]))
            .values(status=CourseStatus.published)
        )
        await s.commit()

    course["status"] = "published"
    course["_module_id"] = mod["id"]
    course["_lesson_ids"] = lesson_ids
    return course
