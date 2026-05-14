import asyncio
import uuid

from tests.conftest import _register_and_login


async def _register_student(client, idx: int) -> dict[str, str]:
    return await _register_and_login(
        client, f"racer{idx}@test.com", "secret123", "student"
    )


# ── Enrollment — happy path & role checks ─────────────────────────────────────


async def test_student_can_enroll_in_published_course(
    client, instructor_headers, student_headers, make_published_course
):
    course = await make_published_course()
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["course_id"] == course["id"]
    assert body["status"] == "active"
    assert body["completed_at"] is None


async def test_instructor_cannot_enroll_returns_403(
    client, instructor_headers, make_published_course
):
    course = await make_published_course()
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=instructor_headers
    )
    assert resp.status_code == 403


async def test_enroll_in_missing_course_returns_404(client, student_headers):
    fake = uuid.uuid4()
    resp = await client.post(
        f"/api/v1/courses/{fake}/enroll", headers=student_headers
    )
    assert resp.status_code == 404


async def test_cannot_enroll_in_draft_course_returns_409(
    client, instructor_headers, student_headers
):
    resp = await client.post(
        "/api/v1/courses",
        headers=instructor_headers,
        json={"title": "draft course"},
    )
    course = resp.json()
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
    )
    assert resp.status_code == 409


async def test_cannot_enroll_in_archived_course_returns_409(
    client, instructor_headers, student_headers, make_published_course
):
    course = await make_published_course()
    await client.delete(
        f"/api/v1/courses/{course['id']}", headers=instructor_headers
    )
    resp = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
    )
    assert resp.status_code == 409


async def test_duplicate_enrollment_returns_409(
    client, instructor_headers, student_headers, make_published_course
):
    course = await make_published_course()
    first = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
    )
    assert second.status_code == 409


# ── Capacity & race conditions ────────────────────────────────────────────────


async def test_capacity_full_returns_409(
    client, instructor_headers, student_headers, make_published_course
):
    course = await make_published_course(max_students=1)
    r1 = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
    )
    assert r1.status_code == 201
    other = await _register_student(client, 99)
    r2 = await client.post(
        f"/api/v1/courses/{course['id']}/enroll", headers=other
    )
    assert r2.status_code == 409


async def test_concurrent_enrollment_respects_capacity(
    client, instructor_headers, make_published_course
):
    course = await make_published_course(title="Race", max_students=3)
    racers = [await _register_student(client, i) for i in range(10)]

    async def attempt(headers):
        return await client.post(
            f"/api/v1/courses/{course['id']}/enroll", headers=headers
        )

    results = await asyncio.gather(*(attempt(h) for h in racers))
    success = [r for r in results if r.status_code == 201]
    full = [r for r in results if r.status_code == 409]
    assert len(success) == 3, [r.status_code for r in results]
    assert len(full) == 7


# ── Listing /me ───────────────────────────────────────────────────────────────


async def test_list_my_enrollments_returns_own_only(
    client, instructor_headers, student_headers, make_published_course
):
    course1 = await make_published_course(title="A")
    course2 = await make_published_course(title="B")
    await client.post(
        f"/api/v1/courses/{course1['id']}/enroll", headers=student_headers
    )
    await client.post(
        f"/api/v1/courses/{course2['id']}/enroll", headers=student_headers
    )

    other = await _register_student(client, 1)
    await client.post(
        f"/api/v1/courses/{course1['id']}/enroll", headers=other
    )

    resp = await client.get("/api/v1/enrollments/me", headers=student_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    titles = {e["course_title"] for e in body}
    assert titles == {"A", "B"}
    for e in body:
        assert e["progress_summary"]["completed_lessons"] == 0


async def test_instructor_cannot_list_enrollments_returns_403(
    client, instructor_headers
):
    resp = await client.get("/api/v1/enrollments/me", headers=instructor_headers)
    assert resp.status_code == 403


# ── Lesson completion ─────────────────────────────────────────────────────────


async def test_mark_lesson_complete_happy_path(
    client, instructor_headers, student_headers, make_published_course
):
    course = await make_published_course()
    lid = course["_lesson_ids"][0]
    enroll = (
        await client.post(
            f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
        )
    ).json()
    resp = await client.post(
        f"/api/v1/enrollments/{enroll['id']}/progress/{lid}",
        headers=student_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["lesson_id"] == lid
    assert body["enrollment_id"] == enroll["id"]


async def test_mark_lesson_complete_is_idempotent(
    client, instructor_headers, student_headers, make_published_course
):
    course = await make_published_course()
    lid = course["_lesson_ids"][0]
    enroll = (
        await client.post(
            f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
        )
    ).json()
    r1 = await client.post(
        f"/api/v1/enrollments/{enroll['id']}/progress/{lid}",
        headers=student_headers,
    )
    r2 = await client.post(
        f"/api/v1/enrollments/{enroll['id']}/progress/{lid}",
        headers=student_headers,
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


async def test_mark_lesson_from_other_course_returns_404(
    client, instructor_headers, student_headers, make_published_course
):
    course_a = await make_published_course(title="A")
    course_b = await make_published_course(title="B")
    lesson_b = course_b["_lesson_ids"][0]
    enroll_a = (
        await client.post(
            f"/api/v1/courses/{course_a['id']}/enroll", headers=student_headers
        )
    ).json()
    resp = await client.post(
        f"/api/v1/enrollments/{enroll_a['id']}/progress/{lesson_b}",
        headers=student_headers,
    )
    assert resp.status_code == 404


async def test_cannot_mark_other_students_enrollment_returns_403(
    client, instructor_headers, student_headers, make_published_course
):
    course = await make_published_course()
    lid = course["_lesson_ids"][0]
    enroll = (
        await client.post(
            f"/api/v1/courses/{course['id']}/enroll", headers=student_headers
        )
    ).json()
    other = await _register_student(client, 7)
    resp = await client.post(
        f"/api/v1/enrollments/{enroll['id']}/progress/{lid}",
        headers=other,
    )
    assert resp.status_code == 403


# ── Auto-completion ───────────────────────────────────────────────────────────


async def test_enrollment_auto_completes_when_all_lessons_done(
    client, instructor_headers, student_headers, make_published_course
):
    course = await make_published_course()
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
    me = (await client.get("/api/v1/enrollments/me", headers=student_headers)).json()
    assert me[0]["status"] == "active"
    assert me[0]["progress_summary"]["completed_lessons"] == 1
    assert me[0]["progress_summary"]["total_lessons"] == 2

    await client.post(
        f"/api/v1/enrollments/{enroll['id']}/progress/{lesson2}",
        headers=student_headers,
    )
    me = (await client.get("/api/v1/enrollments/me", headers=student_headers)).json()
    assert me[0]["status"] == "completed"
    assert me[0]["completed_at"] is not None
    assert me[0]["progress_summary"]["percent"] == 100.0
