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

### Dev seed users (Docker)

After `docker compose up`, `migrate` creates two users if they don't exist (see `SEED_DEV_USERS`, `DEV_ADMIN_*`, `DEV_INSTRUCTOR_*` in `.env`):

| Role | Email | Password |
|---|---|---|
| admin | `admin@smartcourse.local` | `SmartCourseAdmin1!` |
| instructor | `instructor@smartcourse.local` | `SmartCourseInstruct1!` |

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@smartcourse.local&password=SmartCourseAdmin1!"
```

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

### Re-index a published course (owner or admin)

Re-chunks and re-embeds all lessons without running the full publish workflow. Requires `status=published`. Enqueues Celery task `tasks.reindex_course`.

```bash
curl -X POST http://localhost:8000/api/v1/courses/$COURSE_ID/reindex \
  -H "Authorization: Bearer $TOKEN"
```

Returns **202 Accepted** with `{ "status": "accepted", "course_id": "...", "task": "tasks.reindex_course" }`. Use after editing lesson content on an already-published course. **409** if course is not published.

### Soft-delete (archive) a course

```bash
curl -X DELETE http://localhost:8000/api/v1/courses/$COURSE_ID \
  -H "Authorization: Bearer $TOKEN"
```

Sets `status = archived` rather than deleting — preserves enrollment and progress history.

---

## Prerequisites

A course can require other courses to be **completed** before a student may enroll. Managed by the course owner (or admin); enforced at enrollment.

### List a course's prerequisites

```bash
curl http://localhost:8000/api/v1/courses/$COURSE_ID/prerequisites \
  -H "Authorization: Bearer $TOKEN"
```

Returns the prerequisite courses (`id`, `title`, `status`). Visible to anyone who can view the course.

### Add a prerequisite (owner or admin)

```bash
curl -X POST http://localhost:8000/api/v1/courses/$COURSE_ID/prerequisites \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "prerequisite_id": "'"$OTHER_COURSE_ID"'" }'
```

Returns **201** with the updated prerequisite list. Idempotent (a duplicate edge is a no-op). Errors: **422** if the prerequisite is the course itself or doesn't exist; **409** if adding it would create a cycle (A requires B requires A); **403** if not the owner.

### Remove a prerequisite (owner or admin)

```bash
curl -X DELETE http://localhost:8000/api/v1/courses/$COURSE_ID/prerequisites/$PREREQ_ID \
  -H "Authorization: Bearer $TOKEN"
```

Returns **204**.

**Enrollment gate:** `POST /courses/{id}/enroll` returns **422** with the list of missing courses if the student hasn't *completed* every prerequisite. The check runs inside the same `SELECT ... FOR UPDATE` enrollment transaction.

---

## Recommendations

### Recommended courses (student-only)

```bash
curl "http://localhost:8000/api/v1/courses/recommendations?limit=10" \
  -H "Authorization: Bearer $STUDENT_TOKEN"
```

Returns published courses the student is **eligible for** (every prerequisite completed) and **not already enrolled in**, ranked by popularity (total enrollment count, descending). Each item includes `id`, `title`, `description`, `status`, and `popularity`. Instructors/admins get **403**.

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

Returns `201 ProgressResponse`. **Idempotent** — calling again with the same `(enrollment_id, lesson_id)` returns the same row, still `201`, no `409`. When the last lesson is completed, the enrollment auto-flips to `status=completed` with `completed_at` set in the same transaction, and a **certificate** row is issued idempotently (`certificates.enrollment_id` UNIQUE).

Errors:
- `404` if the enrollment doesn't exist or the lesson is not in the enrolled course
- `403` if the enrollment belongs to another student

---

## Certificates

Issued automatically when a student completes every lesson in a course. One certificate per enrollment.

### List my certificates (student-only)

```bash
curl "http://localhost:8000/api/v1/certificates/me?limit=20&offset=0" \
  -H "Authorization: Bearer $STUDENT_TOKEN"
```

Response items include `id`, `enrollment_id`, `course_id`, `issued_at`, and denormalized `course_title`. Instructors and admins receive **403** on this endpoint.

---

## Search

Semantic search over indexed lesson chunks (pgvector). Content must be indexed first — publish the course so the Temporal pipeline extracts, chunks, and embeds lessons.

### Semantic search (optional course scope)

```bash
curl -X POST http://localhost:8000/api/v1/search/semantic \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what are gatekeepers?",
    "course_id": "'"$COURSE_ID"'",
    "limit": 5
  }'
```

Omit `course_id` to search across all indexed content (admin/instructor use). Returns ranked chunks with similarity scores and lesson metadata.

### Global search (my courses only)

```bash
curl -X POST http://localhost:8000/api/v1/search/my \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "query": "distributed systems", "limit": 10 }'
```

Scopes results to courses the caller can access: students see enrolled courses, instructors see owned courses, admins see all.

---

## Assistant

Both endpoints stream Server-Sent Events. Each frame's `data:` field is a JSON-encoded token string; a final `data: [DONE]` frame closes the stream.

### RAG Q&A (any authenticated user)

```bash
curl -N -X POST http://localhost:8000/api/v1/assistant/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "'"$COURSE_ID"'",
    "question": "What is the main theme of the intro lesson?"
  }'
```

Grounded answers come only from retrieved lesson chunks. Off-topic questions receive a refusal without calling the LLM when no relevant chunks are found.

### Instructor content generation (instructor or admin, course owner)

```bash
curl -N -X POST http://localhost:8000/api/v1/assistant/generate \
  -H "Authorization: Bearer $INSTRUCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "'"$COURSE_ID"'",
    "kind": "summary",
    "lesson_id": null
  }'
```

| Field | Values | Notes |
|---|---|---|
| `kind` | `"summary"` \| `"quiz"` | Different system prompts; quiz outputs markdown with A–D options |
| `lesson_id` | UUID or `null` | `null` = whole-course scope via semantic retrieval; set to target one lesson's chunks |

Requires course ownership (or admin). Returns **403** if not the owner, **404** if course not found. Indexed content must exist (`lesson_chunks` rows from a prior publish).

---

## Uploads

Presigned PUT URL for lesson media — bytes go directly to MinIO, not through the API.

```bash
curl -X POST http://localhost:8000/api/v1/uploads \
  -H "Authorization: Bearer $INSTRUCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "lecture.pdf",
    "content_type": "application/pdf"
  }'
```

Response:
```json
{
  "upload_url": "http://localhost:9000/smartcourse/...",
  "storage_key": "lessons/abc123/lecture.pdf"
}
```

Upload with `PUT` to `upload_url`, then pass `storage_key` in `LessonCreate` when adding the lesson.

---

## Admin metrics

All endpoints require **admin** role.

### Overview counts

```bash
curl http://localhost:8000/api/v1/admin/metrics/overview \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Enrollments over time

```bash
curl "http://localhost:8000/api/v1/admin/metrics/enrollments-over-time?days=30" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Popular courses

```bash
curl "http://localhost:8000/api/v1/admin/metrics/popular-courses?limit=10" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Completion metrics

```bash
curl http://localhost:8000/api/v1/admin/metrics/completion \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Recent activity (Mongo event log)

```bash
curl "http://localhost:8000/api/v1/admin/metrics/recent-activity?limit=20" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Pipeline health (failed-events / workflow issues)

```bash
curl http://localhost:8000/api/v1/admin/metrics/pipeline-health \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Returns `status` (`healthy` | `degraded` | `critical`), unsent outbox counts, oldest pending age, and operator hints. Prometheus gauge: `smartcourse_outbox_pending` (also on Grafana **Events pipeline** dashboard).

---

## Event pipeline (background)

Not HTTP endpoints — documented for operators tracing enrollments and completions.

| Component | Role |
|---|---|
| Outbox + relay | Durably stages events; publishes to Kafka with `traceparent` header |
| `welcome-email-consumer` | Kafka → Celery for `user.enrolled` |
| `celery-worker` | Sends welcome email via SMTP (Mailhog in dev — UI http://localhost:8025) |
| `events-archiver` | All `events.*` topics → MongoDB |

Welcome email env: `SMTP_HOST`, `SMTP_PORT`, `SMTP_ENABLED` (see `.env.example`). Disable with `SMTP_ENABLED=false` to log-only.

---

## Observability endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | public | Liveness probe |
| `GET /metrics` | public | Prometheus scrape target (request, DB, LLM, outbox metrics) |

Local UIs (when `docker-compose up -d` is running):

| Service | URL |
|---|---|
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Jaeger | http://localhost:16686 |
| Mailhog | http://localhost:8025 |
| Kafka UI | http://localhost:8081 |
| Temporal UI | http://localhost:8080 |

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
| 409 | Conflict — duplicate email/enrollment, invalid status transition, duplicate `order_index`, prerequisite cycle |
| 422 | Validation failure (bad payload, wrong types, missing fields) — or business rule: prerequisites not met / invalid prerequisite |
| 500 | Unexpected server error — always logged with full traceback |
