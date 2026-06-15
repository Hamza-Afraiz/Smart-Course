# SmartCourse

Intelligent learning platform — a FastAPI async backend with a React + Vite single-page frontend. Part of a 5-week mentored engineering assignment focused on distributed-systems design.

**Current status:** All 5 weeks complete — enrollment, Temporal publish, Kafka events, observability, pgvector retrieval, RAG Q&A, instructor summary/quiz generation, and Tier 2 polish (Mailhog email, certificates, traceparent, re-index, dev seed users). React UI for the full flow. See [docs/PROGRESS.md](docs/PROGRESS.md) for the tracker.

## Repository layout

```
Smart-Course/
  backend/      # FastAPI app, Alembic migrations, Temporal worker, pytest suite,
                #   Dockerfile + docker-compose.yml (full stack incl. Kafka, Mongo, Ollama, observability)
  frontend/     # React + Vite + TypeScript SPA
  docs/         # PRD, API reference, schema, week plans, Q&A log
```

Backend and frontend are independent — each has its own dependencies and dev server. See [backend/](backend/) and [frontend/README.md](frontend/README.md).

---

## Architecture

### High-level

```
┌─────────────┐
│   Client    │  (browser / mobile / curl)
└──────┬──────┘
       │ HTTP + JWT
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI app (async)                       │
│                                                                 │
│   Routers ──▶ Services ──▶ Repositories ──▶ SQLAlchemy ORM     │
│   (HTTP)      (business)   (DB queries)     (models)            │
└──────┬───────────────────┬───────────────┬─────────────────────┘
       │                   │               │
       ▼                   ▼               ▼
┌────────────┐      ┌────────────┐   ┌────────────┐
│ PostgreSQL │      │   Redis    │   │  RabbitMQ  │
│ (truth)    │      │ (cache)    │   │ (queue)    │
└────────────┘      └────────────┘   └────────────┘
```

PostgreSQL is the source of truth. Redis, RabbitMQ, Kafka, Temporal, MongoDB, MinIO, and Ollama are wired for caching, events, workflows, analytics, media storage, and local LLM inference.

### Layered request flow

```
HTTP request
   │
   ▼
[ Router ]       parses input, calls service, converts domain errors → HTTPException
   │
   ▼
[ Service ]      business logic, ownership checks, status transitions
   │
   ▼
[ Repository ]   raw DB queries via AsyncSession
   │
   ▼
[ Model ]        SQLAlchemy 2.0 ORM (Mapped / mapped_column)
   │
   ▼
PostgreSQL
```

A request body is validated by Pydantic schemas before hitting the router. Auth and DB session are injected via FastAPI `Depends()` — see [backend/app/dependencies.py](backend/app/dependencies.py).

### Database schema

7 tables — see [docs/SCHEMA.md](docs/SCHEMA.md) for full ER diagram, indexes, and cascade rules.

```
users ─┬─< courses ─< modules ─< lessons
       │             │
       └─< enrollments ─< progress
                    │
                    └─< certificates
```

---

## Tech stack

| Layer | Choice |
|---|---|
| Web framework | FastAPI 0.115 (async) |
| Database | PostgreSQL 15 (source of truth) |
| ORM | SQLAlchemy 2.0 async + Alembic migrations |
| DB driver | psycopg 3 (async) |
| Validation | Pydantic v2 |
| Auth | JWT (python-jose) + bcrypt |
| Cache | Redis 7 (Week 2+) |
| Message queue | RabbitMQ (Celery broker, Week 3) |
| Workflow engine | Temporal (Week 2) |
| Event streaming | Kafka (Week 3) |
| Testing | pytest + pytest-asyncio + httpx |

---

## Prerequisites

- Python 3.11+
- Docker Desktop (running)
- Git

---

## Setup

### 1. Clone

```bash
git clone <repo-url>
cd Smart-Course
```

### 2. Environment file

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set `SECRET_KEY` to any long random string. Everything else works as-is for local dev.

**Dev seed users** — `migrate` runs `app.scripts.seed_dev_users` after Alembic. Default logins (override in `.env`):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@smartcourse.local` | `SmartCourseAdmin1!` |
| Instructor | `instructor@smartcourse.local` | `SmartCourseInstruct1!` |

Set `SEED_DEV_USERS=false` to skip. Register additional students via the UI or `POST /auth/register`.

### 3. Start the backend (Docker — recommended)

```bash
cd backend
docker-compose up -d --build    # reads backend/.env
docker-compose ps               # all services should be healthy
```

One command brings up the whole backend: postgres, redis, rabbitmq, temporal, temporal-ui, **mailhog**, `migrate` (Alembic + dev seed, then exits), `api` (port 8000), `worker`, relay, Kafka consumers, and celery-worker. `api` and `worker` are the same image (`backend/Dockerfile`) with different commands; source is bind-mounted, so host edits hot-reload both.

DB connection (DBeaver / psql):
```
Host: localhost  Port: 5432  DB: smartcourse  User: smartcourse  Password: smartcourse
```

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The Vite dev server proxies `/api` → `http://localhost:8000`, so the backend must be running. See [frontend/README.md](frontend/README.md) for details.

### Alternative: run the backend on the host

For host-style dev (uvicorn/worker in your own terminals, only infra in Docker):

```bash
cd backend
python3 -m venv venv
source venv/bin/activate                                  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
docker-compose up -d postgres redis rabbitmq temporal temporal-ui   # infra only, by name
alembic upgrade head
uvicorn app.main:app --reload --port 8000                 # terminal 1
python -m app.workers.temporal_worker                     # terminal 2
```

Don't run the host `uvicorn` while the `api` container is also up — they both bind port 8000.

---

## Verify it works

| What | URL |
|---|---|
| Health check | http://localhost:8000/health |
| Swagger UI (try endpoints here) | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

---

## API overview

All routes live under `/api/v1/`. Auth uses OAuth2 password flow (form data); everything else uses JSON.

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/auth/register` | Register a new user | public |
| POST | `/auth/login` | Get JWT access token | public |
| GET | `/users/me` | Own profile | any |
| PATCH | `/users/me` | Update own profile | any |
| GET | `/users/{user_id}` | Get user by id | admin |
| POST | `/courses` | Create a course | instructor |
| GET | `/courses` | List published courses (paginated) | any |
| GET | `/courses/mine` | List courses owned by the caller (any status) | instructor / admin |
| GET | `/courses/{id}` | Course detail | any |
| PATCH | `/courses/{id}` | Update course; status: draft→archived, published→archived only | owner / admin |
| POST | `/courses/{id}/publish` | Start Temporal publish workflow | instructor / admin |
| GET | `/courses/{id}/publish/status` | Publish workflow status | instructor / admin |
| POST | `/courses/{id}/reindex` | Re-chunk/embed a published course (202, Celery) | owner / admin |
| DELETE | `/courses/{id}` | Soft-delete (archive) | owner / admin |
| POST | `/courses/{id}/modules` | Add module | owner / admin |
| GET | `/courses/{id}/modules` | List modules | any |
| POST | `/courses/{id}/modules/{mid}/lessons` | Add lesson | owner / admin |
| GET | `/courses/{id}/modules/{mid}/lessons` | List lessons in a module | any (course-visibility) |
| POST | `/courses/{id}/enroll` | Enroll in a course | student |
| GET | `/enrollments/me` | List own enrollments + progress summary | student |
| GET | `/enrollments/{eid}/progress` | List completed-lesson rows for an enrollment | student (owner) |
| POST | `/enrollments/{eid}/progress/{lid}` | Mark a lesson complete (idempotent); issues certificate when course done | student (owner) |
| GET | `/certificates/me` | List certificates for completed enrollments | student |
| POST | `/search/semantic` | Semantic search over lesson chunks (optional course scope) | any |
| POST | `/search/my` | Global search across enrolled/owned courses | any |
| POST | `/assistant/ask` | RAG Q&A over a course (SSE stream) | any |
| POST | `/assistant/generate` | Instructor summary or quiz from indexed content (SSE) | instructor / admin |
| POST | `/uploads` | Presigned URL for lesson file upload (MinIO) | instructor / admin |
| GET | `/admin/metrics/overview` | Platform counts | admin |
| GET | `/admin/metrics/enrollments-over-time` | Daily enrollment series | admin |
| GET | `/admin/metrics/popular-courses` | Top courses by enrollment | admin |
| GET | `/admin/metrics/completion` | Completion rate + avg time | admin |
| GET | `/admin/metrics/recent-activity` | Latest events from Mongo log | admin |
| GET | `/admin/metrics/pipeline-health` | Outbox backlog + pipeline status (PRD §5) | admin |

Full request/response examples and error codes → [docs/API.md](docs/API.md).
Interactive docs while server is running → [http://localhost:8000/docs](http://localhost:8000/docs).
Demo walkthrough + UC checklist → [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md).

### Observability (local dev)

| What | URL |
|---|---|
| Grafana dashboards | http://localhost:3000 (login `admin` / `admin`) |
| Prometheus | http://localhost:9090 |
| Jaeger traces | http://localhost:16686 |
| Mailhog (welcome emails) | http://localhost:8025 |
| Kafka UI | http://localhost:8081 |
| Temporal UI | http://localhost:8080 |
| RabbitMQ management | http://localhost:15672 |
| MinIO console | http://localhost:9001 |

---

## Running tests

Run from the `backend/` directory with the venv active:

```bash
pytest                                    # all tests
pytest -v                                 # verbose
pytest --cov=app --cov-report=term-missing  # with coverage
```

The first run creates a separate `smartcourse_test` database automatically. Each test gets a fresh schema for full isolation.

---

## Services & profiles

`docker-compose up -d` (from `backend/`) starts the full stack — infra, Temporal, Kafka, Mongo, MinIO, Ollama, Mailhog, observability, migrate (Alembic + seed), api, worker, relay, celery-worker, and event consumers. No profile flags required for core functionality.

### Useful

```bash
docker-compose logs -f api worker     # follow specific services
docker-compose ps                     # health of everything
docker-compose down                   # stop the stack (volumes persist)
```

The API connects to Temporal on startup (`TEMPORAL_HOST`). If Temporal is unreachable the app still starts; `POST .../publish` returns **503** until it's back.

First run pulls the Ollama model (`llama3.2:1b` by default) via the `ollama-pull` init container — allow a few minutes on a cold start.

---

## Project structure

```
backend/
  app/
    routers/         # HTTP layer — auth, users, courses, enrollments, certificates, search, assistant, uploads, metrics
    services/        # Business logic — auth, course, enrollment, certificate, search, RAG, LLM, email, indexing, metrics
    repositories/    # DB queries — user, course, enrollment, certificate, search repos
    models/          # SQLAlchemy ORM models (one file per table)
    schemas/         # Pydantic v2 request/response schemas
    temporal/        # Temporal workflows + activities (course publishing saga)
    workers/         # Temporal worker, outbox relay, Kafka consumers, Celery
    dependencies.py  # FastAPI dependency injection (JWT auth, DB session, roles)
    config.py        # Settings loaded from .env via pydantic-settings
    database.py      # Async engine + AsyncSessionLocal factory
    exceptions.py    # Domain exceptions (services raise, routers convert)
    main.py          # FastAPI app, lifespan, middleware, router registration
  alembic/           # Database migrations
  observability/     # Prometheus, Grafana dashboards, blackbox config
  tests/             # Pytest suite
  requirements.txt   # production deps  (requirements-dev.txt adds test + lint tooling)
  Dockerfile         # one image, run as migrate / api / worker / relay / consumers
  docker-compose.yml # full stack
frontend/
  src/
    api/             # axios client + typed wrappers (courses, assistant, search, generation, uploads)
    auth/            # AuthContext — JWT + /users/me, no server session
    components/      # Layout, GlobalSearch, shared UI primitives
    pages/           # Login, Register, Catalog, CourseDetail (+ AssistantPanel, GenerationPanel), MyCertificates, AdminMetrics
docs/                # PART_A (verbatim spec), PRD + traceability, schema, week plans, Q&A log
```

---

## Design rules (enforced throughout)

- Router → Service → Repository — no skipping layers
- Domain exceptions in services; only routers raise `HTTPException`
- Pydantic schemas separate from ORM models (never return ORM models directly)
- `async` everywhere — `AsyncSession`, `httpx`, bcrypt offloaded to executor
- DB-level constraints for invariants (unique enrollment, unique order_index) — never application-level checks
- Soft delete via status enum — preserves FK integrity
- All routes under `/api/v1/` from day one
