# SmartCourse — Progress Tracker

Single source of truth for what's done and what's next across all 5 weeks. Update this doc whenever a milestone moves.

**Last updated:** 2026-05-14
**Current focus:** Week 2 complete + React UI added for end-to-end testing — Week 3 (events + observability) next

---

## Part A — Core Platform (Weeks 1–3)

### 🟢 Week 1 — Foundation + Core Services — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| Project scaffold + directory structure | ✅ | Router → Service → Repository |
| Docker Compose (postgres, redis, rabbitmq) | ✅ | All healthy on `docker-compose up -d` |
| Dependencies pinned (`requirements.txt`, `requirements-dev.txt`) | ✅ | FastAPI 0.115, SQLAlchemy 2.0, psycopg3 |
| `.env.example` with all config keys | ✅ | |
| SQLAlchemy models — 7 tables | ✅ | users, courses, modules, lessons, enrollments, progress, certificates |
| Alembic initial migration | ✅ | Generated + applied |
| `POST /auth/register` | ✅ | bcrypt hashing, role assignment |
| `POST /auth/login` | ✅ | OAuth2 form, returns JWT |
| `GET /users/me`, `PATCH /users/me` | ✅ | |
| `GET /users/{user_id}` (admin only) | ✅ | |
| JWT auth + role-based dependency injection | ✅ | `CurrentUser`, `InstructorUser`, `AdminUser` aliases |
| Course CRUD — 5 endpoints | ✅ | Create, list, get, update, soft-delete |
| Modules — POST + GET (list) | ✅ | `order_index` uniqueness enforced at DB level |
| Lessons — POST | ✅ | |
| Status transitions enforced | ✅ | Publish via `POST .../publish` (Temporal); PATCH: `draft → archived`, `published → archived` only |
| Ownership checks (service layer) | ✅ | `_can_modify(user, course)` |
| Test suite | ✅ | 47+ tests passing (users, courses, enrollments, Temporal publish), function-scoped DB isolation |
| README + architecture diagram | ✅ | |
| `docs/API.md` reference | ✅ | |
| `docs/SCHEMA.md` ER diagram | ✅ | |
| First git commit | ✅ | |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [x] Service structure defined
- [x] Database schema created
- [x] Basic APIs working
- [x] Local setup ready

---

### 🟢 Week 2 — Enrollment + Publishing Workflow — ✅ COMPLETE

#### Chunk A — Enrollment system — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| `POST /courses/{id}/enroll` endpoint | ✅ | Student-only, returns 201 EnrollmentResponse |
| Atomic enrollment inside DB transaction | ✅ | `SELECT ... FOR UPDATE` on courses row serializes capacity check + insert |
| Duplicate enrollment caught by DB UNIQUE constraint | ✅ | `IntegrityError` → `AlreadyEnrolledError` → 409 |
| `GET /enrollments/me` — student's enrollments | ✅ | Includes course title + progress summary (`total/completed/percent`) |
| `POST /enrollments/{id}/progress/{lesson_id}` — mark lesson complete | ✅ | Idempotent — second call returns the same row with 201, no 409 |
| Enrollment capacity check (`max_students`) | ✅ | Row-lock + count, validated by concurrent race test (10 racers, cap=3 → exactly 3 succeed) |
| Auto-completion of enrollment | ✅ | Last lesson completion flips status=completed + completed_at in same txn |
| Tests for enrollment race conditions | ✅ | `test_concurrent_enrollment_respects_capacity` via `asyncio.gather` |

#### Chunk B — Temporal publishing workflow — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| Temporal SDK installed + worker running | ✅ | `temporal`, `temporal-ui` + `worker` all in `docker-compose up -d` (one image — see `backend/Dockerfile`) |
| Publishing workflow (Temporal) | ✅ | `validate_course_activity` → `process_lessons_activity` → `mark_published_activity` |
| Compensation logic | ✅ | If `mark_published` fails after process, `delete_processed_data_activity` clears `processed_at` |
| `POST /courses/{id}/publish` — kicks off workflow | ✅ | 202 + `{ workflow_id }`; duplicate → 409 |
| `GET /courses/{id}/publish/status` | ✅ | Maps Temporal describe → status payload |
| `courses.processed_at` + migration | ✅ | Set in process activity (placeholder for Week 4 pipeline) |
| Tests for workflow happy path + compensation | ✅ | `tests/test_temporal_publish.py` + `publish_helpers` |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [x] Enrollment flow working reliably
- [x] Workflow orchestration integrated
- [x] Course state transitions handled (PATCH cannot set `published`; use publish endpoint)

#### Frontend UI (testing client, not on the original week plan) — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| Repo split into `backend/` + `frontend/` | ✅ | All Python moved under `backend/`; infra `docker-compose.yml` stays at root |
| React + Vite + TypeScript SPA | ✅ | axios client, `AuthContext`, role-aware routing + guards |
| Stateless-JWT auth model on the client | ✅ | Token in `localStorage`; role always re-read from `/users/me`, never trusted from the token |
| Pages: Login, Register, Catalog, CourseDetail, MyCourses, MyEnrollments, Profile | ✅ | Student + instructor/admin flows end-to-end |
| Supporting backend read endpoints | ✅ | `GET /courses/mine`, `GET /courses/{id}/modules/{mid}/lessons`, `GET /enrollments/{eid}/progress` — expose existing data the UI needs |

---

### 🔴 Week 3 — Event-Driven + Observability — ⬜ NOT STARTED

| Item | Status | Notes |
|---|---|---|
| Kafka cluster up (`docker-compose --profile week3`) | ⬜ | KRaft mode, Bitnami image |
| Kafka producer for `user.enrolled` | ⬜ | Emitted after enrollment commits |
| Kafka producer for `course.published` | ⬜ | Emitted by Temporal workflow on success |
| Kafka producer for `lesson.completed` | ⬜ | |
| Schema registry / event schemas | ⬜ | Versioned, backward compatible |
| Idempotency keys on every event | ⬜ | Consumer-side dedup |
| Celery worker process | ⬜ | RabbitMQ broker (already up) |
| Celery task: send enrollment confirmation email | ⬜ | (stub email — log to console) |
| Celery task: update analytics aggregates | ⬜ | Reads from existing tables |
| Analytics endpoints | ⬜ | Enrollments per course, completion rate, etc. |
| Prometheus metrics endpoint | ⬜ | Request count, latency, error rate |
| OpenTelemetry tracing | ⬜ | Trace through router → service → repo → DB |
| Grafana dashboards | ⬜ | At least: requests, errors, DB connections |
| Jaeger UI for traces | ⬜ | |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [ ] Event-driven flows working
- [ ] Analytics pipeline initialized
- [ ] Basic monitoring and tracing available

---

## Part B — GenAI Layer (Weeks 4–5)

### 🟣 Week 4 — Retrieval Layer — ⬜ NOT STARTED

| Item | Status | Notes |
|---|---|---|
| MongoDB container in docker-compose | ⬜ | `lesson_chunks` collection |
| Mongo connection layer | ⬜ | Motor (async driver) |
| Chunking pipeline (Celery task) | ⬜ | Split lesson text → chunks |
| Triggered by `lesson.created` Kafka event | ⬜ | |
| OpenAI embeddings API integration | ⬜ | Embed each chunk |
| Vector store choice + setup | ⬜ | pgvector OR Mongo Atlas Vector Search |
| Retrieval endpoint (`POST /search`) | ⬜ | Semantic search across enrolled content |
| Tests for chunking + retrieval | ⬜ | |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [ ] Content indexed for semantic search
- [ ] Relevant data retrieval working

---

### 🔵 Week 5 — AI Assistant — ⬜ NOT STARTED

| Item | Status | Notes |
|---|---|---|
| RAG Q&A endpoint (`POST /assistant/ask`) | ⬜ | Streaming response |
| Context retrieval from vector store | ⬜ | Top-K chunks per query |
| Prompt template + safety guardrails | ⬜ | |
| Instructor content generation — lesson summary | ⬜ | |
| Instructor content generation — quiz from lesson | ⬜ | |
| Streaming response via SSE or chunked HTTP | ⬜ | |
| Latency benchmarks | ⬜ | Time-to-first-token, total time |
| Tests for prompt design + response quality | ⬜ | |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [ ] Functional AI assistant
- [ ] Context-aware responses
- [ ] Smooth user interaction flow

---

## Final Deliverables Checklist (end of Week 5)

- [x] Week 1 complete and ready for mentor review
- [ ] All modules completed and reviewed by mentor
- [ ] Codebase clean and well-structured
- [ ] README + technical documentation complete
- [ ] Key workflows working end-to-end
- [ ] Comfortable explaining design decisions

---

## How to use this doc

- Update the **Status** column from ⬜ → 🚧 (in progress) → ✅ (done) as work progresses
- Update **Last updated** at the top whenever you make a change
- When a week is complete, move to the next and update **Current focus**
- This doc, `git log`, and the test suite together tell the full story
