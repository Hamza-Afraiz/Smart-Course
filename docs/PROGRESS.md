# SmartCourse — Progress Tracker

Single source of truth for what's done and what's next across all 5 weeks. Update this doc whenever a milestone moves.

**Last updated:** 2026-05-13
**Current focus:** Week 1 complete — ready for mentor review

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
| Status transitions enforced | ✅ | `draft → published`, `draft/published → archived` only |
| Ownership checks (service layer) | ✅ | `_can_modify(user, course)` |
| Test suite | ✅ | 27 tests passing, function-scoped DB isolation |
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

### 🟡 Week 2 — Enrollment + Publishing Workflow — ⬜ NOT STARTED

| Item | Status | Notes |
|---|---|---|
| `POST /courses/{id}/enroll` endpoint | ⬜ | Student-only |
| Atomic enrollment + progress init in one transaction | ⬜ | If progress init fails, no enrollment row |
| Duplicate enrollment caught by DB UNIQUE constraint | ⬜ | Model is ready, endpoint isn't |
| `GET /enrollments/me` — student's enrollments | ⬜ | |
| `POST /enrollments/{id}/progress/{lesson_id}` — mark lesson complete | ⬜ | |
| Enrollment capacity check (`max_students`) | ⬜ | Race-safe — use `SELECT ... FOR UPDATE` or count-after-insert |
| Temporal SDK installed + worker running | ⬜ | `docker-compose --profile week2 up -d` |
| Publishing workflow (Temporal) | ⬜ | Multi-step: validate → process lessons → publish |
| Compensation logic | ⬜ | If publish fails, revert draft status |
| `POST /courses/{id}/publish` — kicks off workflow | ⬜ | Returns workflow id |
| Tests for enrollment race conditions | ⬜ | Concurrent requests for last seat |
| Tests for workflow happy path + compensation | ⬜ | |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [ ] Enrollment flow working reliably
- [ ] Workflow orchestration integrated
- [ ] Course state transitions handled

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
