# SmartCourse API

Intelligent learning platform backend — FastAPI + PostgreSQL + Redis + RabbitMQ.

---

## Prerequisites

- Python 3.11+
- Docker Desktop (running)
- Git

---

## Setup

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd Smart-Course
```

### 2. Create environment file

```bash
cp .env.example .env
```

Open `.env` and set a real `SECRET_KEY` (any long random string). Everything else works as-is for local dev.

### 3. Create virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 4. Start infrastructure services

Make sure Docker Desktop is running, then:

```bash
docker-compose up -d
```

Wait ~10 seconds for Postgres, Redis, and RabbitMQ to become healthy:

```bash
docker-compose ps   # all three should show "healthy"
```

### 5. Run database migrations

```bash
alembic upgrade head
```

This creates all tables in PostgreSQL. You can verify in DBeaver or psql:

```
Host: localhost  Port: 5432  DB: smartcourse  User: smartcourse  Password: smartcourse
```

### 6. Start the API server

```bash
uvicorn app.main:app --reload --port 8000
```

---

## Verify it works

| What | URL |
|---|---|
| Health check | http://localhost:8000/health |
| Swagger UI (interactive docs) | http://localhost:8000/docs |
| ReDoc (read-only docs) | http://localhost:8000/redoc |

---

## Running tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

---

## Week 2 services (Temporal)

```bash
docker-compose --profile week2 up -d
```

## Week 3 services (Kafka)

```bash
docker-compose --profile week3 up -d
```

---

## Project structure

```
app/
  routers/        # HTTP layer — request/response only
  services/       # Business logic
  repositories/   # All database queries
  models/         # SQLAlchemy ORM models
  schemas/        # Pydantic request/response schemas
  dependencies.py # FastAPI dependency injection (auth, DB session)
  config.py       # Settings loaded from .env
  database.py     # Async engine and session factory
alembic/          # Database migrations
docs/             # Architecture notes and Q&A log
tests/            # Pytest test suite
docker-compose.yml
```
