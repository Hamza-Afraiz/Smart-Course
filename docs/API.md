# SmartCourse API Reference

All routes live under `/api/v1/`. Login uses OAuth2 password flow (form data); everything else uses JSON.

Interactive docs are available at [http://localhost:8000/docs](http://localhost:8000/docs) when the server is running.

---

## Auth

### Register

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@test.com",
    "password": "secret123",
    "full_name": "Alice",
    "role": "instructor"
  }'
```

Roles: `student` | `instructor` | `admin`. Password minimum 8 characters.

### Login → get JWT token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@test.com&password=secret123"
```

Response:
```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

Use the token on every protected endpoint via `Authorization: Bearer <token>`.

---

## Users

### Get own profile

```bash
curl http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"
```

### Update own profile

```bash
curl -X PATCH http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "full_name": "Alice Updated" }'
```

Both `full_name` and `password` are optional — send only what you want to change.

### Get user by ID (admin only)

```bash
curl http://localhost:8000/api/v1/users/$USER_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Courses

### Create a course (instructor only)

```bash
curl -X POST http://localhost:8000/api/v1/courses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Intro to Distributed Systems",
    "description": "Foundations of scalable backend design",
    "max_students": 50
  }'
```

Course starts in `draft` status.

### List published courses (paginated)

```bash
curl "http://localhost:8000/api/v1/courses?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

`limit` must be between 1 and 100. Only `published` courses are returned.

### List my courses (instructor or admin)

```bash
curl "http://localhost:8000/api/v1/courses/mine?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

Returns every course owned by the caller — `draft`, `published`, and `archived` — newest first. Students get 403. Declared before `/{course_id}` so `mine` is never parsed as a course id.

### Get a single course

```bash
curl http://localhost:8000/api/v1/courses/$COURSE_ID \
  -H "Authorization: Bearer $TOKEN"
```

Drafts and archived courses are visible only to the owner or admins; others get 404.

### Update a course (owner or admin only)

```bash
curl -X PATCH http://localhost:8000/api/v1/courses/$COURSE_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "title": "Renamed title", "status": "archived" }'
```

Allowed PATCH status transitions: `draft → archived`, `published → archived`. Setting `status` to `published` via PATCH is **not** allowed (returns **409** with a message pointing to the publish endpoint). To publish, use `POST .../publish` below.

### Publish a course (Temporal workflow, instructor or admin)

Requires Temporal server reachable from the app (`TEMPORAL_HOST` in `.env`). A **Temporal worker** must be running (`python -m app.workers.temporal_worker`) on task queue `course-publishing`.

Prerequisites: course is `draft`, owned by the instructor passed into validation, and has at least one lesson.

```bash
curl -X POST http://localhost:8000/api/v1/courses/$COURSE_ID/publish \
  -H "Authorization: Bearer $TOKEN"
```

Returns **202 Accepted** with `{ "workflow_id": "publish-<uuid>" }`. If a publish workflow for that course is already running, returns **409**.

### Publish workflow status

```bash
curl http://localhost:8000/api/v1/courses/$COURSE_ID/publish/status \
  -H "Authorization: Bearer $TOKEN"
```

Uses the deterministic workflow id `publish-<course_id>`. Returns **404** if no workflow exists for that id yet.

### Soft-delete (archive) a course

```bash
curl -X DELETE http://localhost:8000/api/v1/courses/$COURSE_ID \
  -H "Authorization: Bearer $TOKEN"
```

Sets `status = archived` rather than deleting — preserves enrollment and progress history.

---

## Modules

### Add a module to a course

```bash
curl -X POST http://localhost:8000/api/v1/courses/$COURSE_ID/modules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "title": "Module 1: Foundations", "order_index": 0 }'
```

`order_index` must be unique per course (DB-enforced, returns 409 on duplicates).

### List modules of a course

```bash
curl http://localhost:8000/api/v1/courses/$COURSE_ID/modules \
  -H "Authorization: Bearer $TOKEN"
```

Returned in ascending `order_index` order.

---

## Lessons

### Add a lesson to a module

```bash
curl -X POST http://localhost:8000/api/v1/courses/$COURSE_ID/modules/$MODULE_ID/lessons \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Intro video",
    "order_index": 0,
    "content_type": "video",
    "content_url": "https://cdn.example.com/intro.mp4",
    "duration_seconds": 600
  }'
```

`content_type` values: `video` | `text` | `pdf`. All content fields are optional except `title` and `order_index`.

### List lessons in a module

```bash
curl http://localhost:8000/api/v1/courses/$COURSE_ID/modules/$MODULE_ID/lessons \
  -H "Authorization: Bearer $TOKEN"
```

Returned in ascending `order_index` order. Visibility follows the course: published courses are readable by anyone; drafts/archived only by the owner or an admin (others get `404`). `404` if the module is not in the given course.

---

## Enrollments

Enrollment is student-only. Instructors and admins receive 403.

### Enroll in a course

```bash
curl -X POST http://localhost:8000/api/v1/courses/$COURSE_ID/enroll \
  -H "Authorization: Bearer $STUDENT_TOKEN"
```

Returns `201 EnrollmentResponse` with `status="active"`. Race-safe — the courses row is locked with `SELECT ... FOR UPDATE` while capacity is checked, so concurrent enrollments cannot exceed `max_students`. Duplicate attempts return `409` (DB UNIQUE on `(student_id, course_id)`). Draft or archived courses return `409`.

### List my enrollments (student-only)

```bash
curl "http://localhost:8000/api/v1/enrollments/me?limit=20&offset=0" \
  -H "Authorization: Bearer $STUDENT_TOKEN"
```

Each item includes `course_title` and a `progress_summary` of `{ total_lessons, completed_lessons, percent }`.

### List progress for an enrollment (student-only)

```bash
curl http://localhost:8000/api/v1/enrollments/$ENROLLMENT_ID/progress \
  -H "Authorization: Bearer $STUDENT_TOKEN"
```

Returns a list of `ProgressResponse` — one row per completed lesson (`lesson_id`, `completed_at`), oldest first. Use it to render per-lesson completion state. `404` if the enrollment doesn't exist, `403` if it belongs to another student.

### Mark a lesson as complete

```bash
curl -X POST http://localhost:8000/api/v1/enrollments/$ENROLLMENT_ID/progress/$LESSON_ID \
  -H "Authorization: Bearer $STUDENT_TOKEN"
```

Returns `201 ProgressResponse`. **Idempotent** — calling again with the same `(enrollment_id, lesson_id)` returns the same row, still `201`, no `409`. When the last lesson is completed, the enrollment auto-flips to `status=completed` with `completed_at` set in the same transaction.

Errors:
- `404` if the enrollment doesn't exist or the lesson is not in the enrolled course
- `403` if the enrollment belongs to another student

---

## Error responses

All errors follow FastAPI's default shape:

```json
{ "detail": "Human-readable message" }
```

| Code | Meaning |
|---|---|
| 401 | Missing or invalid JWT, or wrong login credentials |
| 403 | Authenticated but lacks role / ownership |
| 404 | Resource not found (or hidden — draft courses look 404 to non-owners) |
| 409 | Conflict — duplicate email, invalid status transition, duplicate `order_index` |
| 422 | Pydantic validation failure (bad payload, wrong types, missing fields) |
| 500 | Unexpected server error — always logged with full traceback |
