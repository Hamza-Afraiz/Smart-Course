# SmartCourse — Demo Runbook & UC Checklist

Use this for mentor review or a live walkthrough. Stack must be up: `cd backend && docker compose up -d`.

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:5173 | `cd frontend && npm run dev` |
| API / Swagger | http://localhost:8000/docs | |
| Grafana | http://localhost:3000 | `admin` / `admin` |
| Jaeger | http://localhost:16686 | Cross-service traces after enroll |
| Mailhog | http://localhost:8025 | Welcome emails from enrollment |
| Temporal UI | http://localhost:8080 | Publish workflows |
| Kafka UI | http://localhost:8081 | `events.*` topics |
| MinIO console | http://localhost:9001 | Uploaded lesson media |

---

## Pre-demo setup (5 min)

1. Start stack: `cd backend && docker compose up -d --build` (first run: Ollama model pull may take a few minutes).
2. Start frontend: `cd frontend && npm run dev`
3. **Log in with seeded users** (created by `migrate` — no manual registration required):
   - **Admin:** `admin@smartcourse.local` / `SmartCourseAdmin1!`
   - **Instructor:** `instructor@smartcourse.local` / `SmartCourseInstruct1!`
   - **Student:** register one via UI (`student@demo.com`) or API if you need a fresh student account.
4. As instructor: create a course with **text lesson** content (inline `content_text` or upload PDF/video), add module + lesson.
5. Publish course → wait for Temporal workflow (Temporal UI → `publish-<course_id>` completed).
6. As student: enroll in the published course → check **Mailhog** for welcome email within ~30s.

---

## UC checklist (click path)

| UC | Actor | Steps | Pass? |
|----|-------|-------|-------|
| UC-01 | Guest | Register student (optional — seed users cover admin/instructor) | ☐ |
| UC-02 | User | Login → JWT in client (seed admin or instructor) | ☐ |
| UC-03 | User | Profile page / PATCH name | ☐ |
| UC-04 | Admin | Swagger `GET /users/{id}` with admin token | ☐ |
| UC-05 | Instructor | Create course, modules, lessons | ☐ |
| UC-06 | Instructor | Archive draft; publish via button | ☐ |
| UC-07 | Student | Catalog lists published only | ☐ |
| UC-08 | Student | Course detail visible when published | ☐ |
| UC-09 | Student | Enroll → 201; duplicate → 409; welcome email in Mailhog | ☐ |
| UC-10 | Student | My enrollments + progress % | ☐ |
| UC-11 | Student | Mark all lessons complete → enrollment `completed` | ☐ |
| UC-11b | Student | My Learning → **Certificates** nav or course complete link | ☐ |
| UC-12 | Instructor | Publish → 202 + workflow; status endpoint | ☐ |
| UC-12b | Instructor | `POST /courses/{id}/reindex` (202) after editing lesson content | ☐ |
| UC-13 | System | Enroll → outbox row → Kafka (pipeline health + Jaeger trace) | ☐ |
| UC-14 | Operator | Grafana + Jaeger + Admin Metrics (pipeline health section) | ☐ |
| UC-15 | User | Course search panel or global search | ☐ |
| UC-16 | Student | Ask this course (assistant panel) | ☐ |
| UC-17 | Instructor | Instructor tools → summary or quiz | ☐ |

---

## Failure-mode demos (optional, high impact)

### Outbox backlog (failed-events story)

1. Open Grafana → **Events pipeline** dashboard → note **Outbox backlog = 0**.
2. Stop relay: `docker compose stop relay`
3. Enroll a student → outbox row created, not sent.
4. Admin → **Metrics** → **Event pipeline health** → status `degraded` or `critical`, pending count ↑.
5. Start relay: `docker compose start relay` → backlog drains to 0.

### Cross-service tracing (Tier 2)

1. Enroll a student (with relay + consumers running).
2. Jaeger → search service `welcome-email-consumer` or `celery-worker`.
3. Trace should share `trace_id` with the original `POST .../enroll` span (via `traceparent` in outbox → Kafka → Celery).

### Welcome email path

1. Enroll → open Mailhog http://localhost:8025.
2. Confirm subject `Welcome to <course title>` within ~30s.
3. If missing: check `welcome-email-consumer`, `celery-worker`, and relay logs.

### Publish compensation

1. Temporal UI → failed publish workflow (or inject test failure if configured).
2. Course remains `draft`; `processed_at` cleared on compensation.

### Re-index without re-publish

1. Edit lesson text on a **published** course.
2. `POST /api/v1/courses/{id}/reindex` as owner → 202.
3. Search / assistant should reflect new content after Celery task completes.

### Assistant slowness

1. Jaeger → trace `POST /assistant/ask` → child span `gen_ai.chat llama3.2:1b`.
2. Show `prompt_eval` dominates on CPU — not Postgres.

---

## Ops quick reference

| Symptom | Check |
|---------|--------|
| Publish 503 | Temporal up? Worker running? `docker compose ps worker temporal` |
| No search / empty assistant | Course published once? `lesson_chunks` populated? Try re-index |
| Events not in Mongo | `events-archiver` consumer up? Kafka UI topics? |
| No welcome email | Mailhog up? `celery-worker` + `welcome-email-consumer` running? |
| Slow LLM | Ollama healthy? Grafana LLM/RAG dashboard; use lesson scope for generate |
| Outbox growing | Relay + Kafka health; `GET /admin/metrics/pipeline-health` |
| Seed login fails | Re-run migrate: `docker compose run --rm migrate` |

---

## Load baseline

Run `./scripts/load_baseline.sh` and record p95 in [LOAD_BASELINE.md](LOAD_BASELINE.md).

---

## Key API endpoints (reference)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/auth/login` | JWT (seed admin/instructor) |
| POST | `/api/v1/courses/{id}/publish` | Temporal publish → chunk/embed |
| POST | `/api/v1/courses/{id}/reindex` | Re-chunk/embed published course (Celery) |
| GET | `/api/v1/certificates/me` | Student certificates |
| GET | `/api/v1/admin/metrics/pipeline-health` | Outbox backlog + pipeline status |
| POST | `/api/v1/assistant/ask` | RAG Q&A (SSE) |
| POST | `/api/v1/assistant/generate` | Instructor summary/quiz (SSE) |

Full curl examples → [API.md](API.md).
