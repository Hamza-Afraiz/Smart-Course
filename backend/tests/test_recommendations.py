import pytest_asyncio

from tests.conftest import _register_and_login
from tests.course_helpers import make_published_course_direct


@pytest_asyncio.fixture
async def make_published_course(client, engine, instructor_headers):
    async def _factory(*, title: str = "Course", max_students: int | None = None):
        return await make_published_course_direct(
            client, engine, instructor_headers, title=title, max_students=max_students
        )

    return _factory


async def _enroll(client, headers, course_id) -> dict:
    r = await client.post(f"/api/v1/courses/{course_id}/enroll", headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_recommends_published_not_enrolled(
    client, student_headers, make_published_course
):
    a = await make_published_course(title="A")
    b = await make_published_course(title="B")
    resp = await client.get("/api/v1/courses/recommendations", headers=student_headers)
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()}
    assert {a["id"], b["id"]} <= ids


async def test_excludes_already_enrolled(
    client, student_headers, make_published_course
):
    a = await make_published_course(title="A")
    b = await make_published_course(title="B")
    await _enroll(client, student_headers, a["id"])
    ids = {
        c["id"]
        for c in (
            await client.get("/api/v1/courses/recommendations", headers=student_headers)
        ).json()
    }
    assert a["id"] not in ids
    assert b["id"] in ids


async def test_excludes_courses_with_unmet_prerequisites(
    client, instructor_headers, student_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    await client.post(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": intro["id"]},
    )
    ids = {
        c["id"]
        for c in (
            await client.get("/api/v1/courses/recommendations", headers=student_headers)
        ).json()
    }
    assert advanced["id"] not in ids  # blocked by unmet prerequisite
    assert intro["id"] in ids         # eligible


async def test_includes_course_after_completing_prerequisite(
    client, instructor_headers, student_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    await client.post(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": intro["id"]},
    )
    enrollment = await _enroll(client, student_headers, intro["id"])
    for lesson_id in intro["_lesson_ids"]:
        r = await client.post(
            f"/api/v1/enrollments/{enrollment['id']}/progress/{lesson_id}",
            headers=student_headers,
        )
        assert r.status_code == 201, r.text
    ids = {
        c["id"]
        for c in (
            await client.get("/api/v1/courses/recommendations", headers=student_headers)
        ).json()
    }
    assert advanced["id"] in ids   # prerequisite now satisfied
    assert intro["id"] not in ids  # already completed


async def test_ordered_by_popularity(
    client, student_headers, make_published_course
):
    quiet = await make_published_course(title="Quiet")
    popular = await make_published_course(title="Popular")
    for i in range(3):
        h = await _register_and_login(client, f"rec{i}@test.com", "secret123", "student")
        await _enroll(client, h, popular["id"])
    body = (
        await client.get("/api/v1/courses/recommendations", headers=student_headers)
    ).json()
    ids = [c["id"] for c in body]
    assert ids.index(popular["id"]) < ids.index(quiet["id"])
    pop_row = next(c for c in body if c["id"] == popular["id"])
    assert pop_row["popularity"] == 3


async def test_instructor_cannot_get_recommendations(client, instructor_headers):
    resp = await client.get(
        "/api/v1/courses/recommendations", headers=instructor_headers
    )
    assert resp.status_code == 403
