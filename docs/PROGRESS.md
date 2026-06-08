# SmartCourse — Progress Tracker

Single source of truth for what's done and what's next across all 5 weeks. Update this doc whenever a milestone moves.

**Last updated:** 2026-06-05
**Current focus:** ALL 5 WEEKS COMPLETE. Part A (foundation, enrollment+Temporal, event-driven+observability) + Part B (Week 4 retrieval: chunking/embeddings/pgvector over text+pdf+video; Week 5 RAG Q&A via Ollama) done. Plus: React UI, dual-source media (URL + MinIO upload), extraction cache, prod k8s manifests + HPA + ExternalSecret.

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

### 🟢 Week 3 — Event-Driven + Observability — ✅ COMPLETE

**Built:** transactional outbox + relay → Kafka; 3 events (`user.enrolled`, `lesson.completed` via outbox; `course.published` direct from a Temporal activity); welcome-email consumer + Celery worker; `processed_events` consumer-side dedupe; MongoDB `events` archiver (raw interaction log); 5 admin analytics endpoints (Postgres + Mongo); Prometheus `/metrics` + Grafana dashboard; structured JSON logs across all 6 services; OpenTelemetry → Jaeger tracing (request + DB child spans, `trace_id` in logs). All three failure modes (Kafka outage, duplicate, consumer downtime) stress-tested and pass.

**Known extension (not blocking Week 3's bar):** cross-service trace propagation across the async boundary. Today each service produces its own traces and the synchronous API→DB path is one linked trace; stitching API→relay→Kafka→consumer→Celery into a *single* trace needs context propagation — inject `traceparent` into the outbox row, carry it in the Kafka message header, and restore it in the consumer. Documented in docs/QA.md.

#### Original checklist (for reference)

**Suggested execution order** (proves the pattern on one event before scaling out — avoids the "everything is 80% done, nothing works" failure mode):

1. **Pick `user.enrolled` and walk backwards from the consumer.** The welcome-email task tells you what the payload needs. Design the event schema (idempotency key + thin payload of IDs only).
2. **Outbox table + atomic emit.** Add `outbox` table; `enrollment_service.enroll()` inserts the event row in the same Postgres transaction as the enrollment row. Now event emission is ACID-atomic with the business write — no dual-write problem at this layer.
3. **Verify atomic emit standalone.** Enroll a user, confirm the outbox row is there. Don't bring Kafka in yet.
4. **Outbox relay** — separate process polls `outbox WHERE sent_at IS NULL`, publishes to Kafka, marks `sent_at`. At-least-once delivery; durable across crashes because the row stays until the relay confirms the send.
5. **Kafka + consumer + dedupe + welcome-email Celery task** — first event end-to-end. `processed_events` table on consumer side (or Redis with TTL) catches duplicates from relay retries / consumer rebalances. Result: effectively-once.
6. **Stress-test failure modes** before scaling out: kill Kafka mid-relay (verify retry), inject a duplicate (verify dedupe skip), crash the consumer mid-process (verify offset behavior). Trust the pattern before copying it.
7. **Replicate for `lesson.completed`** (outbox in `enrollment_service.complete_lesson`) and **`course.published`** (emitted from inside the Temporal workflow as an activity — no outbox needed there because Temporal already provides durable orchestration; just give the activity an idempotency key).
8. **Analytics endpoints** — SQL rollups over Postgres core tables + the Mongo `events` log (storage decision per QA.md "Final storage architecture"). Materialized views for the slower aggregates.
9. **Observability** — Prometheus `/metrics` + structured JSON logs early (cheap, useful for debugging the work above). Full OpenTelemetry + Jaeger last, once flows are stable enough to be worth instrumenting.

| Item | Status | Notes |
|---|---|---|
| `user.enrolled` event schema + outbox table | 🚧 | Step 1–2 of the order above |
| Atomic outbox emit from `enrollment_service.enroll` | ⬜ | Same DB transaction as the enrollment row |
| Outbox relay process (poll → Kafka → mark sent) | ⬜ | At-least-once; survives crashes |
| Kafka cluster up | ⬜ | Still gated by `week3` profile until consumer is ready |
| Kafka producer (driven by the relay) | ⬜ | Emitted from outbox, not from request path |
| `processed_events` dedupe table | ⬜ | Consumer-side idempotency |
| Celery worker + welcome-email task | ⬜ | First side-effect task; logs to console as stub |
| End-to-end smoke test for `user.enrolled` | ⬜ | Prove the pattern before replicating |
| Kafka producer for `course.published` | ⬜ | Emitted from inside the Temporal activity — no outbox needed (Temporal IS durable) |
| Kafka producer for `lesson.completed` | ⬜ | Outbox in `complete_lesson` |
| Analytics endpoints | ⬜ | SQL rollups + Mongo `events` log |
| Mongo `events` collection (raw interaction log) | ⬜ | Per QA.md "Final storage architecture" |
| Prometheus `/metrics` endpoint | ⬜ | Request count, latency, error rate, DB pool |
| Structured JSON logging | ⬜ | With `trace_id` correlation field |
| OpenTelemetry tracing | ⬜ | FastAPI + SQLAlchemy + Kafka + Temporal instrumentation |
| Grafana dashboards + Jaeger UI | ⬜ | Last; instrument once flows are stable |

**Deliverables (from EXECUTION_GUIDELINES.md):**
- [ ] Event-driven flows working
- [ ] Analytics pipeline initialized
- [ ] Basic monitoring and tracing available

---

## Part B — GenAI Layer (Weeks 4–5)

### 🟣 Week 4 — Retrieval Layer — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| pgvector + `lesson_chunks` table (vector(384), HNSW) | ✅ | `pgvector/pgvector:pg15` image |
| Chunking (tiktoken, sentence-aware, ~400 tok + overlap) | ✅ | `chunking_service.py` |
| Embeddings (sentence-transformers all-MiniLM-L6-v2, local/free) | ✅ | `embedding_service.py`, warm-up at worker start |
| Extraction: text inline, pdf (pypdf), video (faster-whisper / YouTube) | ✅ | `extraction_service.py`; URL + uploaded-file paths |
| Wired into Temporal `process_lessons_activity` (replaced stub) | ✅ | extract → chunk → embed → bulk insert; idempotent |
| Semantic search endpoint `POST /search/semantic` | ✅ | cosine `<=>`, course-scoped |
| Dual-source media (paste URL OR upload to MinIO) + extraction cache | ✅ | bonus beyond plan |
| Verified: video upload → Whisper transcript → chunk → semantic match | ✅ | Sintel: "guards the land" matched "gatekeepers" with no shared words |

### 🔵 Week 4 (original heading retained below) — superseded by the table above

### 🟣 Week 4 — Retrieval Layer — (legacy checklist) — ⬜ NOT STARTED

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

### 🔵 Week 5 — AI Assistant — ✅ COMPLETE

| Item | Status | Notes |
|---|---|---|
| RAG Q&A endpoint `POST /assistant/ask` (SSE streaming) | ✅ | `routers/assistant.py` |
| Retrieval reuses Week 4 search, course-scoped + similarity floor | ✅ | `rag_service.py` |
| LLM via Ollama (llama3.2:3b, local/free) | ✅ | `llm_service.py`; swap to API = one file |
| Grounded prompt + hallucination guardrail | ✅ | answers only from chunks; off-topic → "not in this course" (no LLM call when no hits) |
| Streaming chat UI on course page | ✅ | `AssistantPanel.tsx` + `api/assistant.ts` (fetch SSE reader) |
| Verified grounded answer + guardrail | ✅ | Sintel transcript answered; "capital of France?" refused |

**Note:** instructor content generation (summaries/quizzes) from the original plan is the same RAG pattern with a different prompt — not built, optional extension.

### 🔵 Week 5 — AI Assistant — (legacy checklist) — ⬜ NOT STARTED

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
