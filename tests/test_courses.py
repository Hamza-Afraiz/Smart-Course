async def _create_course(client, headers, title="Test Course", **kwargs):
    payload = {"title": title, **kwargs}
    resp = await client.post("/api/v1/courses", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Course creation + role checks ─────────────────────────────────────────────

async def test_instructor_can_create_course(client, instructor_headers):
    course = await _create_course(client, instructor_headers)
    assert course["status"] == "draft"
    assert course["title"] == "Test Course"


async def test_student_cannot_create_course_returns_403(client, student_headers):
    resp = await client.post(
        "/api/v1/courses",
        headers=student_headers,
        json={"title": "hack attempt"},
    )
    assert resp.status_code == 403


# ── List & visibility ─────────────────────────────────────────────────────────

async def test_list_courses_excludes_drafts(client, instructor_headers, student_headers):
    await _create_course(client, instructor_headers, title="Still a draft")
    resp = await client.get("/api/v1/courses", headers=student_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_published_course_visible_in_list(client, instructor_headers, student_headers):
    course = await _create_course(client, instructor_headers, title="To publish")
    await client.patch(
        f"/api/v1/courses/{course['id']}",
        headers=instructor_headers,
        json={"status": "published"},
    )
    resp = await client.get("/api/v1/courses", headers=student_headers)
    assert len(resp.json()) == 1


async def test_student_cannot_see_draft_returns_404(client, instructor_headers, student_headers):
    course = await _create_course(client, instructor_headers)
    resp = await client.get(f"/api/v1/courses/{course['id']}", headers=student_headers)
    # 404 not 403 — don't leak that the course exists
    assert resp.status_code == 404


async def test_owner_can_view_own_draft(client, instructor_headers):
    course = await _create_course(client, instructor_headers)
    resp = await client.get(f"/api/v1/courses/{course['id']}", headers=instructor_headers)
    assert resp.status_code == 200


# ── Ownership / modification ──────────────────────────────────────────────────

async def test_non_owner_cannot_update_course(
    client, instructor_headers, other_instructor_headers
):
    course = await _create_course(client, instructor_headers)
    resp = await client.patch(
        f"/api/v1/courses/{course['id']}",
        headers=other_instructor_headers,
        json={"title": "stolen"},
    )
    assert resp.status_code == 403


async def test_owner_can_update_course(client, instructor_headers):
    course = await _create_course(client, instructor_headers)
    resp = await client.patch(
        f"/api/v1/courses/{course['id']}",
        headers=instructor_headers,
        json={"title": "Renamed"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"


# ── Status transitions ────────────────────────────────────────────────────────

async def test_invalid_status_transition_returns_409(client, instructor_headers):
    course = await _create_course(client, instructor_headers)
    # archive (draft → archived is allowed)
    await client.patch(
        f"/api/v1/courses/{course['id']}",
        headers=instructor_headers,
        json={"status": "archived"},
    )
    # archived → published is NOT allowed
    resp = await client.patch(
        f"/api/v1/courses/{course['id']}",
        headers=instructor_headers,
        json={"status": "published"},
    )
    assert resp.status_code == 409


async def test_soft_delete_archives_course(client, instructor_headers):
    course = await _create_course(client, instructor_headers)
    resp = await client.delete(
        f"/api/v1/courses/{course['id']}", headers=instructor_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


# ── Modules ───────────────────────────────────────────────────────────────────

async def test_module_duplicate_order_index_returns_409(client, instructor_headers):
    course = await _create_course(client, instructor_headers)
    base = f"/api/v1/courses/{course['id']}/modules"
    r1 = await client.post(base, headers=instructor_headers, json={"title": "m1", "order_index": 0})
    assert r1.status_code == 201
    r2 = await client.post(base, headers=instructor_headers, json={"title": "m2", "order_index": 0})
    assert r2.status_code == 409


async def test_list_modules_returns_in_order(client, instructor_headers):
    course = await _create_course(client, instructor_headers)
    base = f"/api/v1/courses/{course['id']}/modules"
    # insert out of order to verify ordering happens server-side
    await client.post(base, headers=instructor_headers, json={"title": "second", "order_index": 1})
    await client.post(base, headers=instructor_headers, json={"title": "first", "order_index": 0})
    resp = await client.get(base, headers=instructor_headers)
    titles = [m["title"] for m in resp.json()]
    assert titles == ["first", "second"]


# ── Lessons ───────────────────────────────────────────────────────────────────

async def test_lesson_wrong_course_id_returns_404(client, instructor_headers):
    course = await _create_course(client, instructor_headers)
    module = (await client.post(
        f"/api/v1/courses/{course['id']}/modules",
        headers=instructor_headers,
        json={"title": "m", "order_index": 0},
    )).json()
    # use a wrong course_id with the valid module_id
    resp = await client.post(
        f"/api/v1/courses/00000000-0000-0000-0000-000000000000/modules/{module['id']}/lessons",
        headers=instructor_headers,
        json={"title": "lesson", "order_index": 0},
    )
    assert resp.status_code == 404


# ── Pagination validation ─────────────────────────────────────────────────────

async def test_pagination_limit_too_large_returns_422(client, student_headers):
    resp = await client.get("/api/v1/courses?limit=999", headers=student_headers)
    assert resp.status_code == 422


async def test_pagination_limit_zero_returns_422(client, student_headers):
    resp = await client.get("/api/v1/courses?limit=0", headers=student_headers)
    assert resp.status_code == 422
