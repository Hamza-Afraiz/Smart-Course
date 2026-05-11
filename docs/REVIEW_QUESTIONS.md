# SmartCourse — Mentor Review Questions

Self-check before each weekly review. If you can answer these clearly, you're ready.

---

## Week 1 — Foundation

**Database & Transactions**
1. Why must enrollment creation and progress initialization be in one transaction?
2. Give a real example of a race condition in SmartCourse. How does the schema prevent it?
3. How does UNIQUE(student_id, course_id) prevent duplicates even under concurrent requests?
4. Why is MVCC better than row-level locking for high concurrency?
5. What role does WAL play in PostgreSQL transactions? What happens on a crash mid-write?
6. Why did we choose RESTRICT on enrollment FKs instead of CASCADE?

**Architecture**
7. Walk through a POST /enroll request from HTTP → router → service → repository → DB → response.
8. Why does business logic live in the service layer, not the router?
9. What is the difference between a DB connection and a DB session?
10. What does expire_on_commit=False do and why is it critical in async FastAPI?

**Async**
11. What happens if you call time.sleep(2) inside an async FastAPI route?
12. Why can't you use sync SQLAlchemy (db.query()) in an async route?
13. What is the difference between concurrency and parallelism?
14. Why does Python use multiprocessing for CPU-bound work instead of threads?
15. What is the GIL and how does it affect async I/O vs CPU work?

**Tools**
16. What is Uvicorn? What is Gunicorn? How do they work together in production?
17. Why do we need a connection pool? What is pool_size=10 based on?
18. What does pool_pre_ping=True protect against?

---

## Week 2 — Enrollment + Publishing Workflow

1. Why does the publishing workflow use Temporal instead of Celery?
2. What is the Saga/Compensation pattern? Give an example from the publishing workflow.
3. What does "partial failures must not corrupt the publishing workflow" mean in practice?
4. How does Temporal guarantee a workflow completes even after a server restart?
5. Walk through what happens when a student enrolls — synchronous and asynchronous parts.
6. Where do lesson chunks get stored after publishing? Why not PostgreSQL?

---

## Week 3 — Events & Observability

1. What is the difference between Celery and Kafka? When do you use each?
2. Why does Kafka allow multiple consumers but Celery tasks have one?
3. What does idempotency mean for a Celery worker? How do you implement it?
4. How does OpenTelemetry trace a request from FastAPI → DB → Celery worker?
5. What is the difference between metrics (Prometheus) and tracing (Jaeger)?
6. Where does "Failed Events / Workflow Issues" metric come from? Postgres or Prometheus?
7. What is replication lag and when does it matter for SmartCourse?

---

## General System Design

1. When would you add a read replica to SmartCourse?
2. When would you consider sharding? Is SmartCourse at that scale?
3. Why is Redis needed if PostgreSQL already has its own cache?
4. What is backpressure and how does Kafka handle it?
5. Explain the difference between eventual consistency and strong consistency with a SmartCourse example.
