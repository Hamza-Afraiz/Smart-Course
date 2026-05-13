# SmartCourse API

Intelligent learning platform backend — built with FastAPI, PostgreSQL, and an async-first architecture. Part of a 5-week mentored engineering assignment focused on distributed-systems design.

**Current status:** Week 1 complete — see [docs/PROGRESS.md](docs/PROGRESS.md) for the full 5-week tracker.

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

PostgreSQL is the source of truth. Redis and RabbitMQ are wired up for Week 2/3 (caching, Celery, Kafka events, Temporal workflows).

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

A request body is validated by Pydantic schemas before hitting the router. Auth and DB session are injected via FastAPI `Depends()` — see [app/dependencies.py](app/dependencies.py).

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
cp .env.example .env
```

Open `.env` and set `SECRET_KEY` to any long random string. Everything else works as-is for local dev.

### 3. Virtual environment + dependencies

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 4. Start infrastructure

```bash
docker-compose up -d
docker-compose ps               # postgres, redis, rabbitmq should be healthy
```

### 5. Migrations

```bash
alembic upgrade head
```

DB connection (DBeaver / psql):
```
Host: localhost  Port: 5432  DB: smartcourse  User: smartcourse  Password: smartcourse
```

### 6. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

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
| GET | `/courses/{id}` | Course detail | any |
| PATCH | `/courses/{id}` | Update course (incl. status transitions) | owner / admin |
| DELETE | `/courses/{id}` | Soft-delete (archive) | owner / admin |
| POST | `/courses/{id}/modules` | Add module | owner / admin |
| GET | `/courses/{id}/modules` | List modules | any |
| POST | `/courses/{id}/modules/{mid}/lessons` | Add lesson | owner / admin |

Full request/response examples and error codes → [docs/API.md](docs/API.md).
Interactive docs while server is running → [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Running tests

```bash
pytest                                    # all tests
pytest -v                                 # verbose
pytest --cov=app --cov-report=term-missing  # with coverage
```

The first run creates a separate `smartcourse_test` database automatically. Each test gets a fresh schema for full isolation.

---

## Optional services

### Week 2 — Temporal

```bash
docker-compose --profile week2 up -d
```

### Week 3 — Kafka

```bash
docker-compose --profile week3 up -d
```

---

## Project structure

```
app/
  routers/         # HTTP layer — auth.py, users.py, courses.py
  services/        # Business logic — auth_service, user_service, course_service, ...
  repositories/    # DB queries — user_repo, course_repo, module_repo, lesson_repo
  models/          # SQLAlchemy ORM models (one file per table)
  schemas/         # Pydantic v2 request/response schemas
  dependencies.py  # FastAPI dependency injection (JWT auth, DB session, roles)
  config.py        # Settings loaded from .env via pydantic-settings
  database.py      # Async engine + AsyncSessionLocal factory
  exceptions.py    # Domain exceptions (services raise, routers convert)
  main.py          # FastAPI app, lifespan, middleware, router registration
alembic/           # Database migrations
docs/              # PRD, schema, week plans, Q&A log
tests/             # Pytest suite — conftest.py + test_users.py + test_courses.py
docker-compose.yml
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
