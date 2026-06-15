import uuid

import pytest_asyncio

from tests.course_helpers import make_published_course_direct


@pytest_asyncio.fixture
async def make_published_course(client, engine, instructor_headers):
    """Override the conftest fixture with a Temporal-free direct publish."""
    async def _factory(*, title: str = "Course", max_students: int | None = None):
        return await make_published_course_direct(
            client, engine, instructor_headers, title=title, max_students=max_students
        )

    return _factory


async def _complete_course(client, student_headers, course) -> None:
    """Enroll in a published course and complete every lesson → auto-completes."""
    enroll = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
    )
    assert enroll.status_code == 201, enroll.text
    enrollment_id = enroll.json()["id"]
    for lesson_id in course["_lesson_ids"]:
        r = await client.post(
            f"/api/v1/enrollments/{enrollment_id}/progress/{lesson_id}",
            headers=student_headers,
        )
        assert r.status_code == 201, r.text


# ── Managing prerequisites ────────────────────────────────────────────────────


async def test_instructor_can_add_and_list_prerequisite(
    client, instructor_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    resp = await client.post(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": intro["id"]},
    )
    assert resp.status_code == 201, resp.text
    assert [c["id"] for c in resp.json()] == [intro["id"]]

    listed = await client.get(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
    )
    assert listed.status_code == 200
    assert [c["id"] for c in listed.json()] == [intro["id"]]


async def test_add_prerequisite_is_idempotent(
    client, instructor_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    last = None
    for _ in range(2):
        last = await client.post(
            f"/api/v1/courses/{advanced['id']}/prerequisites",
            headers=instructor_headers,
            json={"prerequisite_id": intro["id"]},
        )
        assert last.status_code == 201, last.text
    assert len(last.json()) == 1


async def test_non_owner_cannot_add_prerequisite(
    client, instructor_headers, other_instructor_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    resp = await client.post(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=other_instructor_headers,
        json={"prerequisite_id": intro["id"]},
    )
    assert resp.status_code == 403


async def test_self_prerequisite_rejected(
    client, instructor_headers, make_published_course
):
    course = await make_published_course(title="Solo")
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": course["id"]},
    )
    assert resp.status_code == 422


async def test_nonexistent_prerequisite_rejected(
    client, instructor_headers, make_published_course
):
    course = await make_published_course(title="Solo")
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 422


async def test_cycle_rejected(client, instructor_headers, make_published_course):
    a = await make_published_course(title="A")
    b = await make_published_course(title="B")
    first = await client.post(
        f"/api/v1/courses/{a['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": b["id"]},
    )
    assert first.status_code == 201
    # B requires A would close the loop A→B→A
    second = await client.post(
        f"/api/v1/courses/{b['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": a["id"]},
    )
    assert second.status_code == 409


async def test_transitive_cycle_rejected(
    client, instructor_headers, make_published_course
):
    a = await make_published_course(title="A")
    b = await make_published_course(title="B")
    c = await make_published_course(title="C")
    # A requires B, B requires C
    for course, prereq in ((a, b), (b, c)):
        r = await client.post(
            f"/api/v1/courses/{course['id']}/prerequisites",
            headers=instructor_headers,
            json={"prerequisite_id": prereq["id"]},
        )
        assert r.status_code == 201, r.text
    # C requires A would close A→B→C→A
    resp = await client.post(
        f"/api/v1/courses/{c['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": a["id"]},
    )
    assert resp.status_code == 409


async def test_remove_prerequisite(
    client, instructor_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    await client.post(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": intro["id"]},
    )
    resp = await client.delete(
        f"/api/v1/courses/{advanced['id']}/prerequisites/{intro['id']}",
        headers=instructor_headers,
    )
    assert resp.status_code == 204
    listed = await client.get(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
    )
    assert listed.json() == []


# ── Enrollment gate ───────────────────────────────────────────────────────────


async def test_enroll_blocked_when_prerequisite_not_completed(
    client, instructor_headers, student_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    await client.post(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": intro["id"]},
    )
    resp = await client.post(
        f"/api/v1/courses/{advanced['id']}/enroll", headers=student_headers
    )
    assert resp.status_code == 422
    assert "Intro" in resp.json()["detail"]


async def test_enrolled_but_not_completed_prerequisite_still_blocks(
    client, instructor_headers, student_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    await client.post(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": intro["id"]},
    )
    enroll = await client.post(
        f"/api/v1/courses/{intro['id']}/enroll", headers=student_headers
    )
    assert enroll.status_code == 201
    resp = await client.post(
        f"/api/v1/courses/{advanced['id']}/enroll", headers=student_headers
    )
    assert resp.status_code == 422


async def test_enroll_allowed_after_completing_prerequisite(
    client, instructor_headers, student_headers, make_published_course
):
    advanced = await make_published_course(title="Advanced")
    intro = await make_published_course(title="Intro")
    await client.post(
        f"/api/v1/courses/{advanced['id']}/prerequisites",
        headers=instructor_headers,
        json={"prerequisite_id": intro["id"]},
    )
    await _complete_course(client, student_headers, intro)
    resp = await client.post(
        f"/api/v1/courses/{advanced['id']}/enroll", headers=student_headers
    )
    assert resp.status_code == 201, resp.text


async def test_no_prerequisites_enroll_succeeds(
    client, student_headers, make_published_course
):
    course = await make_published_course(title="Open")
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
    )
    assert resp.status_code == 201, resp.text
