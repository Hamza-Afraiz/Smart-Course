# Week 1 Plan — Foundation + Core Services

**Goal:** Stand up a production-grade project skeleton with working User and Course management APIs, a solid database schema, and a fully reproducible local dev environment.

---

## Day-by-Day Breakdown

### Day 1 — Project Scaffold & Local Environment

**Tasks**
- Define the top-level project directory structure
- Write `docker-compose.yml` with:
  - PostgreSQL
  - Redis
  - RabbitMQ
  - (placeholder services for Kafka, Temporal — can be stubbed)
- Create `pyproject.toml` / `requirements.txt` with:
  - FastAPI, Uvicorn
  - SQLAlchemy (async) + Alembic
  - Pydantic v2
  - python-dotenv
  - psycopg (async driver)
- Set up `.env.example` for all config values
- Verify all containers start cleanly

**Deliverable:** `docker-compose up` brings up the full local stack.

---

### Day 2 — Database Schema Design

**Tables to design**

| Table | Key Columns |
|---|---|
| `users` | id, email, hashed_password, role (enum: student/instructor/admin), created_at, is_active |
| `courses` | id, title, description, instructor_id (FK), status (enum: draft/published/archived), created_at, updated_at |
| `modules` | id, course_id (FK), title, order_index, created_at |
| `lessons` | id, module_id (FK), title, content_type (video/text/pdf), content_url, order_index, duration_seconds |
| `enrollments` | id, student_id (FK), course_id (FK), enrolled_at, status (enum: active/completed/dropped), UNIQUE(student_id, course_id) |
| `progress` | id, enrollment_id (FK), lesson_id (FK), completed_at, UNIQUE(enrollment_id, lesson_id) |

**Tasks**
- Write SQLAlchemy ORM models for all tables
- Write Alembic migration for initial schema
- Run migration against local Postgres
- Verify schema with `psql`

**Deliverable:** Database schema applied, migrations tracked in version control.

---

### Day 3 — User Management API

**Endpoints**

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register new user (student or instructor) |
| POST | `/api/v1/auth/login` | Login, return JWT access token |
| GET | `/api/v1/users/me` | Get own profile (auth required) |
| GET | `/api/v1/users/{user_id}` | Get user by ID (admin only) |
| PATCH | `/api/v1/users/me` | Update own profile |

**Implementation details**
- Password hashing with `bcrypt`
- JWT tokens with `python-jose` or `PyJWT`
- Role-based access control middleware (dependency injection in FastAPI)
- Pydantic schemas for request/response validation (separate from ORM models)
- Async DB sessions via SQLAlchemy `AsyncSession`

**Deliverable:** All user endpoints working and testable via Swagger UI (`/docs`).

---

### Day 4 — Course Management API

**Endpoints**

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/courses` | Create course (instructor only) |
| GET | `/api/v1/courses` | List all published courses (paginated) |
| GET | `/api/v1/courses/{course_id}` | Get course detail |
| PATCH | `/api/v1/courses/{course_id}` | Update course (owner only) |
| DELETE | `/api/v1/courses/{course_id}` | Soft-delete / archive course (owner only) |
| POST | `/api/v1/courses/{course_id}/modules` | Add module to course |
| GET | `/api/v1/courses/{course_id}/modules` | List modules |
| POST | `/api/v1/courses/{course_id}/modules/{module_id}/lessons` | Add lesson to module |

**Implementation details**
- Ownership check: only the instructor who created the course can update it
- Course status transitions: `draft → published`, `published → archived`
- Pagination using `limit` + `offset` query params
- Consistent error responses (404, 403, 422)

**Deliverable:** Full course CRUD working end-to-end.

---

### Day 5 — Testing, Cleanup & Documentation

**Tasks**
- Write unit tests for:
  - User registration (duplicate email, invalid role)
  - Course creation (role check, ownership)
  - Course update (non-owner rejection)
- Write a `README.md` covering:
  - Project overview
  - How to run locally (`docker-compose up`)
  - API overview with example curl commands
  - Architecture diagram (basic, can be ASCII or drawn)
- Verify Alembic migrations are clean and reproducible from scratch
- Review code structure — enforce separation of concerns:
  - `routers/` → HTTP layer
  - `services/` → business logic
  - `repositories/` → DB queries
  - `models/` → ORM models
  - `schemas/` → Pydantic models

**Deliverable:** Tests passing, README complete, clean commit history.

---

## Project Structure (Target End of Week 1)

```
smart-course/
├── docker-compose.yml
├── .env.example
├── pyproject.toml
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings from env
│   ├── database.py              # Async engine + session
│   ├── dependencies.py          # Shared FastAPI deps (auth, db session)
│   ├── models/
│   │   ├── user.py
│   │   ├── course.py
│   │   ├── module.py
│   │   ├── lesson.py
│   │   └── enrollment.py
│   ├── schemas/
│   │   ├── user.py
│   │   └── course.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── users.py
│   │   └── courses.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   └── course_service.py
│   └── repositories/
│       ├── user_repo.py
│       └── course_repo.py
├── tests/
│   ├── conftest.py
│   ├── test_users.py
│   └── test_courses.py
└── docs/
    ├── PRD.md
    ├── EXECUTION_GUIDELINES.md
    └── WEEK1_PLAN.md
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| ORM | SQLAlchemy async | Native async support, compatible with FastAPI's async model |
| Auth | JWT (stateless) | Scales horizontally; no session store needed in Week 1 |
| Layered architecture | Router → Service → Repository | Clear separation; services are testable without HTTP layer |
| Soft deletes | `status = archived` on courses | Preserves enrollment/progress history; avoids FK issues |
| UNIQUE constraint on enrollments | DB-level | Prevents duplicate enrollments even under concurrent requests |
| Pagination | limit/offset | Simple for now; can migrate to cursor-based in Week 2+ |

---

## Definition of Done — Week 1

- [ ] `docker-compose up` starts all services cleanly
- [ ] Alembic migration applies schema from scratch
- [ ] All user endpoints return correct responses (tested via Swagger or curl)
- [ ] All course + module + lesson endpoints return correct responses
- [ ] Role-based access control enforced (student cannot create courses)
- [ ] Ownership check enforced (instructor cannot edit another's course)
- [ ] At least one test per major flow passing
- [ ] README written with setup instructions
- [ ] Codebase follows Router → Service → Repository pattern
