# SmartCourse — Product Requirements Document (PRD)

## Overview

SmartCourse is an intelligent, large-scale learning platform designed to support modern digital education for universities, enterprises, and training academies.

---

## Problem Statement

EduCorp's current system suffers from:

- **Slow content publishing** — manual workflows make it difficult for instructors to launch and update courses
- **Poor discoverability** — no intelligent search, contextual assistance, or adaptive learning support
- **Data inconsistency** — course data, user progress, and analytics are scattered across systems
- **High latency under load** — enrollment spikes, notifications, and background tasks degrade performance
- **Underutilized data** — rich course interaction data is not leveraged for recommendations

---

## Business Goals

SmartCourse must provide:

1. **Robust course management** — instructors create/update courses; students browse, enroll, and track progress
2. **Scalable operations backbone** — publishing and enrollment trigger reliable internal workflows
3. **Consistent learner data** — enrollment, progress, completions, and certificates are durable and accurate
4. **Long-term scalability** — supports tens of thousands of concurrent learners with reliable background workflows

---

## Key Use-Cases

| ID | Actor | Goal | Preconditions | Success |
|----|-------|------|---------------|---------|
| UC-01 | Guest | Register as student or instructor | Valid email, password, role | Account created; can log in |
| UC-02 | User | Authenticate and obtain a session token | Registered account | JWT issued |
| UC-03 | Student / Instructor / Admin | View or update own profile | Valid token | `GET/PATCH /users/me` succeeds |
| UC-04 | Admin | Look up another user by ID | Admin role | `GET /users/{id}` succeeds |
| UC-05 | Instructor | Create and manage a course (draft) | Instructor role | Course CRUD; modules and lessons added |
| UC-06 | Instructor | Publish or archive a course with valid transitions | Owns course | Status changes per rules; invalid transitions rejected |
| UC-07 | Student | Browse published courses | Authenticated | Paginated list of published courses only |
| UC-08 | Student | View course detail | Course published, or owns draft, or admin | Appropriate visibility (404 for hidden drafts) |
| UC-09 | Student | Enroll in a published course | Published course; under capacity; not already enrolled | Enrollment created; duplicate/capacity/draft cases rejected |
| UC-10 | Student | List own enrollments with progress summary | Has enrollments | Returns course title and completion stats |
| UC-11 | Student | Mark lessons complete and finish a course | Enrolled; lesson belongs to course | Progress recorded; idempotent; enrollment completes when all lessons done |
| UC-12 | Instructor | Publish course via durable multi-step workflow (planned) | Draft with content | Temporal workflow; partial failure compensated (Week 2 Chunk B) |
| UC-13 | System | Emit and process lifecycle events (planned) | Enrollment / publish / completion | Kafka + consumers; no double-processing (Week 3) |
| UC-14 | Operator | Observe health, metrics, and traces (planned) | Stack running | Prometheus, Grafana, Jaeger, OTel (Week 3) |

---

## Non-Functional Requirements

### Security & privacy

| ID | Requirement | Target / rule | Status |
|----|-------------|---------------|--------|
| NFR-S01 | Password storage | bcrypt hashing; never log passwords | Implemented |
| NFR-S02 | API authentication | JWT; configurable secret and expiry | Implemented |
| NFR-S03 | Authorization | Role-based access; course ownership enforced in service layer | Implemented |
| NFR-S04 | Least information on errors | Draft courses return 404 to non-owners (no existence leak) | Implemented |

### Consistency & durability

| ID | Requirement | Target / rule | Status |
|----|-------------|---------------|--------|
| NFR-C01 | Source of truth | PostgreSQL holds authoritative user, course, enrollment, progress state | Implemented |
| NFR-C02 | Duplicate enrollments | DB `UNIQUE(student_id, course_id)`; surfaced as 409 | Implemented |
| NFR-C03 | Enrollment capacity under concurrency | No over-enrollment when `max_students` set; `SELECT … FOR UPDATE` on course row | Implemented |
| NFR-C04 | Lesson completion idempotency | `UNIQUE(enrollment_id, lesson_id)`; safe retries | Implemented |
| NFR-C05 | Cross-component consistency (enrollment vs analytics) | Enrollment commits independently; analytics eventual (outbox + idempotent consumers) | Planned Week 3 |

### Reliability & operability

| ID | Requirement | Target / rule | Status |
|----|-------------|---------------|--------|
| NFR-R01 | Publishing partial failure | Saga / compensations; course not left corrupted | Planned Week 2 Chunk B (Temporal) |
| NFR-R02 | Background task retry | Celery retries; Kafka consumer idempotency | Planned Week 3 |
| NFR-R03 | Failure diagnosis | Structured logs; metrics; distributed traces | Partial (logging); metrics/traces Week 3 |

### Performance & scalability (Part A trajectory)

| ID | Requirement | Target / rule | Status |
|----|-------------|---------------|--------|
| NFR-P01 | API concurrency model | Async FastAPI + async SQLAlchemy; no blocking I/O in request path | Implemented |
| NFR-P02 | DB connection discipline | Pooled connections; engine dispose on shutdown | Implemented |
| NFR-P03 | Load & latency SLOs | Define p95/p99 per endpoint under load test harness | To be baselined in Week 3 with metrics |
| NFR-P04 | Horizontal API scaling | Stateless API instances; shared Postgres/Redis | Architecture supports; not load-tested yet |

### Maintainability

| ID | Requirement | Target / rule | Status |
|----|-------------|---------------|--------|
| NFR-M01 | Layering | Router → Service → Repository; Pydantic schemas for I/O | Implemented |
| NFR-M02 | Schema migrations | Alembic; reproducible from empty DB | Implemented |
| NFR-M03 | Automated regression | pytest suite against real Postgres schema | Implemented |

---

## Core Functional Requirements

### 1. Course & User Management
- Create and update courses, modules, and learning assets
- User registration with roles: `student`, `instructor`, `admin`
- Student enrollment with rules for:
  - Duplicate enrollment prevention
  - Enrollment limits / prerequisites
  - Enrollment history tracking
- Consistency across all system components on every update/enrollment

### 2. Content Publishing Workflow
- On publish/update, content is analyzed and broken into components (modules, lessons, chunks)
- Data stored for fast retrieval and search
- Course marked as `ready` only after all processing completes
- Partial failures must not corrupt the publishing workflow

### 3. Enrollment Workflow
- On enrollment:
  - Enrollment recorded (published courses only; capacity and duplicate rules enforced).
  - Progress tracked via completion records (`progress` rows on lesson completion); enrollment auto-completes when all lessons in the course are completed.
  - Analytics records updated — **async**, decoupled transaction (Kafka + Celery, Week 3).
  - Notifications (e.g. welcome email) — **async** (Celery, Week 3).
- Must handle: high volume, idempotency, backpressure, failure recovery (idempotency and capacity covered in API; backpressure/events Week 3).

### 4. Distributed & Event-Driven Behaviors
- Content processing after publishing
- Analytics updates after enrollment
- Notification dispatch
- Preparation of course material for intelligent Q&A
- Requirements: run independently, traceable, recoverable, no double-processing, handle spikes

### 5. Analytics Metrics
- Total Students
- Total Instructors
- Total Courses Published
- New Enrollments Over Time
- Course Completion Rate
- Average Time to Complete a Course
- Most Popular Courses
- Average Courses per Student
- Failed Events / Workflow Issues

### 6. System Observability & Reliability
- Clear separation of responsibilities between components
- Monitoring and logging for all key flows
- Ability to diagnose failures in publishing, enrollment, and background tasks
- High consistency and accuracy across all data models

---

## Milestones & Deliverable Traceability

| Milestone | Timebox | Outcomes | Doc / evidence |
|-----------|---------|----------|----------------|
| M1 — Foundation | Week 1 | Users, courses, modules, lessons; JWT; Docker; Alembic | [WEEK1_PLAN.md](WEEK1_PLAN.md), [PROGRESS.md](PROGRESS.md) |
| M2 — Enrollment + publish orchestration | Week 2 | Reliable enrollment + Temporal publishing | [PROGRESS.md](PROGRESS.md), [CLAUDE.md](../CLAUDE.md) (Saga / Temporal) |
| M3 — Events + observability | Week 3 | Kafka, Celery, analytics pipeline, metrics/traces | [EXECUTION_GUIDELINES.md](EXECUTION_GUIDELINES.md) |

Formal PRD submission expectations (from Part A brief):

- **Use-cases:** covered in [Key Use-Cases](#key-use-cases) above.
- **Functional + non-functional:** [Core Functional Requirements](#core-functional-requirements) and [Non-Functional Requirements](#non-functional-requirements).
- **Timeline / milestones:** this table + [EXECUTION_GUIDELINES.md](EXECUTION_GUIDELINES.md).
- **Traceability:** [Requirement traceability matrix](#requirement-traceability-matrix) below.

---

## Requirement traceability matrix

Requirements map to **implementation** (primary module or path) and **verification** (pytest). “Planned” rows are in scope but not shipped yet.

| Req ID | Requirement summary | Implementation | Tests |
|--------|----------------------|----------------|-------|
| FR-1.1 | User registration | `app/routers/auth.py`, `app/services/auth_service.py` | `test_register_*` in `tests/test_users.py` |
| FR-1.2 | Login / JWT | `app/routers/auth.py`, `app/dependencies.py` | `test_login_*` in `tests/test_users.py` |
| FR-1.3 | Profile CRUD + admin user lookup | `app/routers/users.py`, `app/services/user_service.py` | `test_get_me_*`, `test_patch_me_*`, `test_get_user_by_id_*` in `tests/test_users.py` |
| FR-1.4 | Course CRUD + visibility | `app/routers/courses.py`, `app/services/course_service.py` | `test_*course*` in `tests/test_courses.py` |
| FR-1.5 | Modules + lessons | `app/services/module_service.py`, `lesson_service.py` | `test_module_*`, `test_lesson_*`, `test_list_modules_*` in `tests/test_courses.py` |
| FR-1.6 | Student enrollment + capacity + idempotency | `app/services/enrollment_service.py`, `app/repositories/enrollment_repo.py` | `tests/test_enrollments.py` (`test_student_can_enroll_*`, `test_duplicate_*`, `test_capacity_*`, `test_concurrent_*`) |
| FR-1.7 | List enrollments + progress summary | `app/routers/enrollments.py`, `enrollment_service.compute_progress_summary` | `test_list_my_enrollments_*`, `test_instructor_cannot_list_*` |
| FR-1.8 | Lesson completion + auto-complete course | `enrollment_service.complete_lesson`, `progress_repo` | `test_mark_lesson_*`, `test_enrollment_auto_completes_*` |
| FR-2.1 | Publishing workflow (Temporal, compensations) | Planned: `app/workers/` + workflow module | Planned Week 2 Chunk B |
| FR-3.1 | Kafka events + consumers | Planned Week 3 | — |
| FR-3.2 | Celery tasks (notifications, analytics) | Planned Week 3 | — |
| FR-4.1 | Analytics metrics endpoints / aggregates | Planned Week 3 | — |
| FR-5.1 | Prometheus / OTel / Jaeger | Planned Week 3 | — |
| NFR-S01–S04 | Security & authz | `app/config.py`, `dependencies.py`, services | Implicit via role/404 tests in `test_courses.py`, `test_enrollments.py` |
| NFR-C01–C04 | DB consistency & enrollment races | `database.py`, `enrollment_repo.lock_course_for_enrollment` | `test_concurrent_enrollment_respects_capacity`, UNIQUE tests |
| NFR-M01–M03 | Layering, migrations, tests | Repo layout, `alembic/`, `tests/` | Full `pytest` suite |

---

## Expected Outcomes

- All major course lifecycle operations supported
- Reliable background processing (publishing, analytics, notifications)
- High scalability under load
- Strong consistency and failure handling
- High-quality, maintainable architecture

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| API Framework | Python, FastAPI |
| Relational DB | PostgreSQL |
| NoSQL DB | MongoDB / Cassandra |
| Cache | Redis |
| Task Queue | Celery + RabbitMQ |
| Event Streaming | Kafka + Schema Registry |
| Workflow Engine | Temporal |

### Observability
| Tool | Purpose |
|---|---|
| Prometheus + Grafana | Metrics & dashboards |
| Jaeger | Distributed tracing |
| OpenTelemetry | Instrumentation |

### DevOps
- Docker
- Docker Compose

---

## Delivery Scope

### Part A — Core Platform (Weeks 1–3)
Foundational backend: course management, publishing workflows, enrollment, event-driven processing, observability.

### Part B — GenAI Layer (Weeks 4–5)
Intelligent layer: embeddings, vector search, RAG-based Q&A assistant, content generation.
