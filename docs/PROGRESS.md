# SmartCourse — Progress Tracker

Single source of truth for what's done and what's next across all 5 weeks. Update this doc whenever a milestone moves.

**Last updated:** 2026-06-11
**Current focus:** Mentor review prep — deferred PRD-vision features now built (prerequisites, recommendations, Redis cache, schema registry) + frontend + load baseline (NFR-P03); docs synced.

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
| Auto-completion of enrollment | ✅ | Last lesson completion flips status=completed + completed_at; certificate issued idempotently in same txn |
| Tests for enrollment race conditions | ✅ | `test_concurrent_enrollment_respects_capacity` via `asyncio.gather` |

#### Chunk B — Temporal publishing workflow — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| Temporal SDK installed + worker running | ✅ | `temporal`, `temporal-ui` + `worker` all in `docker-compose up -d` (one image — see `backend/Dockerfile`) |
| Publishing workflow (Temporal) | ✅ | `validate_course_activity` → `process_lessons_activity` → `mark_published_activity` |
| Compensation logic | ✅ | If `mark_published` fails after process, `delete_processed_data_activity` clears `processed_at` |
| `POST /courses/{id}/publish` — kicks off workflow | ✅ | 202 + `{ workflow_id }`; duplicate → 409 |
| `GET /courses/{id}/publish/status` | ✅ | Maps Temporal describe → status payload |
| `courses.processed_at` + migration | ✅ | Set in process activity; Week 4 pipeline wired in |
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

### 🟢 Week 3 — Event-Driven + Observability — ✅ COMPLETE

**Built:** transactional outbox + relay → Kafka; 3 events (`user.enrolled`, `lesson.completed` via outbox; `course.published` direct from a Temporal activity); welcome-email consumer + Celery worker (SMTP → Mailhog in dev); `processed_events` consumer-side dedupe; MongoDB `events` archiver (raw interaction log); 6 admin analytics endpoints (Postgres + Mongo + pipeline health); Prometheus `/metrics` + Grafana dashboards; structured JSON logs across all services; OpenTelemetry → Jaeger tracing (request + DB + LLM/RAG + cross-service `traceparent` through outbox → Kafka → consumers → Celery). Failure modes (Kafka outage, duplicate, consumer downtime) stress-tested and pass.

| Item | Status | Notes |
|---|---|---|
| `user.enrolled` event schema + outbox table | ✅ | Thin payload (IDs only) + idempotency key + `traceparent` column |
| Atomic outbox emit from `enrollment_service.enroll` | ✅ | Same DB transaction as the enrollment row |
| Outbox relay process (poll → Kafka → mark sent) | ✅ | `app/workers/outbox_relay.py`; forwards `traceparent` in Kafka headers |
| Kafka cluster up | ✅ | Core in `docker-compose.yml` (not profile-gated) |
| Kafka producer (driven by the relay) | ✅ | Emitted from outbox, not from request path |
| `processed_events` dedupe table | ✅ | Consumer-side idempotency |
| Celery worker + welcome-email task | ✅ | Real SMTP via `email_service` → Mailhog (:8025 UI) |
| Cross-service trace propagation | ✅ | `app/observability/propagation.py`; outbox → Kafka → consumers → Celery |
| End-to-end smoke test for `user.enrolled` | ✅ | Pattern proven before replicating |
| Kafka producer for `course.published` | ✅ | Emitted from Temporal activity (no outbox) |
| Kafka producer for `lesson.completed` | ✅ | Outbox in `complete_lesson` |
| Analytics endpoints | ✅ | `GET /admin/metrics/*` — 6 endpoints incl. pipeline-health |
| Mongo `events` collection (raw interaction log) | ✅ | Archiver consumer writes all events |
| Prometheus `/metrics` endpoint | ✅ | Request count, latency, error rate, DB pool, LLM/RAG, outbox |
| Structured JSON logging | ✅ | With `trace_id` correlation field |
| OpenTelemetry tracing | ✅ | FastAPI + SQLAlchemy + httpx (Ollama) + custom LLM/RAG spans |
| Grafana dashboards + Jaeger UI | ✅ | System, LLM/RAG, infrastructure, events pipeline |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [x] Event-driven flows working
- [x] Analytics pipeline initialized
- [x] Basic monitoring and tracing available

---

## Part B — GenAI Layer (Weeks 4–5)

### 🟣 Week 4 — Retrieval Layer — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| pgvector + `lesson_chunks` table (vector(384), HNSW) | ✅ | `pgvector/pgvector:pg15` image |
| Chunking (tiktoken, sentence-aware, ~400 tok + overlap) | ✅ | `chunking_service.py` |
| Embeddings (sentence-transformers all-MiniLM-L6-v2, local/free) | ✅ | `embedding_service.py`, warm-up at worker start |
| Extraction: text inline, pdf (pypdf), video (faster-whisper / YouTube) | ✅ | `extraction_service.py`; URL + uploaded-file paths |
| Wired into Temporal `process_lessons_activity` (replaced stub) | ✅ | Shared `content_indexing_service`; extract → chunk → embed |
| Re-index published course (without re-publish) | ✅ | `POST /courses/{id}/reindex` → Celery `tasks.reindex_course` |
| Semantic search endpoint `POST /search/semantic` | ✅ | cosine `<=>`, course-scoped |
| Global search `POST /search/my` | ✅ | Scoped to enrolled/owned courses |
| Dual-source media (paste URL OR upload to MinIO) + extraction cache | ✅ | bonus beyond plan |
| Verified: video upload → Whisper transcript → chunk → semantic match | ✅ | Sintel: "guards the land" matched "gatekeepers" with no shared words |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [x] Content indexed for semantic search
- [x] Relevant data retrieval working

---

### 🔵 Week 5 — AI Assistant — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| RAG Q&A endpoint `POST /assistant/ask` (SSE streaming) | ✅ | `routers/assistant.py` |
| Retrieval reuses Week 4 search, course-scoped + similarity floor | ✅ | `rag_service.py` |
| LLM via Ollama (llama3.2:1b default, local/free) | ✅ | `llm_service.py`; swap to API = one file |
| Grounded prompt + hallucination guardrail | ✅ | answers only from chunks; off-topic → "not in this course" |
| Streaming chat UI on course page | ✅ | `AssistantPanel.tsx` + `api/assistant.ts` |
| Instructor content generation — summary | ✅ | `POST /assistant/generate` + `GenerationPanel.tsx` |
| Instructor content generation — quiz | ✅ | Same endpoint, `kind: "quiz"` |
| LLM observability (OTel GenAI spans + Prometheus histograms) | ✅ | TTFT, prompt tokens, tok/s; Grafana LLM/RAG dashboard |
| Verified grounded answer + guardrail | ✅ | Sintel transcript answered; off-topic refused |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [x] Functional AI assistant
- [x] Context-aware responses
- [x] Smooth user interaction flow

---

## Post–Week 5 — Tier 2 (pre-review polish) — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| Mailhog + real welcome email | ✅ | `mailhog` in compose; Celery sends SMTP; UI http://localhost:8025 |
| Certificate issuance on course complete | ✅ | Idempotent row in same txn as enrollment completion |
| `GET /certificates/me` | ✅ | Student-only; includes `course_title` |
| Cross-service `traceparent` | ✅ | Outbox column + Kafka headers + consumer/Celery restore |
| Re-index endpoint | ✅ | `POST /courses/{id}/reindex` (202); published courses only |
| Dev seed users (migrate) | ✅ | `admin@smartcourse.local`, `instructor@smartcourse.local` — see README |
| Frontend for Tier 2 | ✅ | `/my-certificates`, re-index button on course detail, completion links |
| Dedicated Tier 2 pytest | ✅ | `tests/test_tier2.py` — certs, reindex, traceparent, welcome email |

---

## Post-Tier 2 — Deferred PRD-vision features — ✅ COMPLETE (2026-06-11)

The four PRD-vision items previously deferred as out-of-week-plan scope are now all built, tested, and (where user-facing) wired into the frontend.

| Item | Status | Notes |
|---|---|---|
| Course prerequisites | ✅ | Self-referential M2M + DB `CHECK` no-self-loop; recursive-CTE cycle detection; enrolment gated on *completion* of prereqs (422); `POST/GET/DELETE /courses/{id}/prerequisites`; migration `9c5d7e8f2a31` (verified up+down on real Postgres); `tests/test_prerequisites.py` (12) |
| Recommendations | ✅ | `GET /courses/recommendations` — prereq-eligible, not-already-enrolled published courses, ranked by Postgres enrolment count; `tests/test_recommendations.py` (6) |
| Redis hot-path cache | ✅ | Cache-aside on catalog + course detail; generational catalog invalidation; circuit breaker (degrades to Postgres on Redis outage); disabled-under-test; `app/cache.py`; `tests/test_cache.py` (3) |
| Event schema registry | ✅ | In-app contract validation wired into `event_service.emit` + BACKWARD-compatibility checker; `app/events/schema_registry.py`; `tests/test_schema_registry.py` (11). Confluent SR container deferred (rationale in QA.md) |
| Frontend for prereqs + recommendations | ✅ | `PrerequisitePanel` (owner manage · student met/unmet) on course detail; "Recommended for you" row on catalog; `tsc -b && vite build` clean |
| Load/latency baseline (NFR-P03) | ✅ | `scripts/load_baseline.py` run against the live API; p50/p95/p99 + req/s recorded in `docs/LOAD_BASELINE.md` |

All four features + the design concepts behind them (strong vs eventual consistency, fault tolerance, scalability, schema registry, latency percentiles) are logged in `docs/QA.md` (2026-06-09 / 2026-06-11 sessions). 32 new tests pass against real Postgres + Redis.

---

## Final Deliverables Checklist (end of Week 5)

- [x] Week 1 complete and ready for mentor review
- [x] All modules completed (Weeks 1–5)
- [x] Codebase clean and well-structured
- [x] README + technical documentation complete
- [x] Key workflows working end-to-end
- [x] Pre-review hardening: pipeline health API + Grafana, smoke tests, demo runbook
- [x] Tier 2: Mailhog welcome email, certificates, traceparent propagation, re-index endpoint, dev seed users
- [x] Documentation synced (README, API.md, DEMO_RUNBOOK, PROGRESS)
- [ ] Mentor review sign-off (external)

---

## How to use this doc

- Update the **Status** column from ⬜ → 🚧 (in progress) → ✅ (done) as work progresses
- Update **Last updated** at the top whenever you make a change
- When a week is complete, move to the next and update **Current focus**
- This doc, `git log`, and the test suite together tell the full story
