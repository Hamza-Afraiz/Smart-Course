# SmartCourse — Concepts Q&A

Running log of questions asked during the project. Auto-appended each session.

---

## Session 1 — 2026-05-06/07

---

### Q: What are the alternatives to Docker Compose and their tradeoffs?

**A:**

| Tool | Best For | Avoid If |
|---|---|---|
| **Docker Compose** | Local multi-service dev, standard choice | You need K8s parity |
| **Podman Compose** | Rootless/daemonless Linux setups | Mac development |
| **Tilt** | Teams needing live UI + hot reload loops | Solo projects — overkill |
| **Skaffold** | Kubernetes-native CI/CD dev loops | You're not targeting K8s |
| **minikube/kind** | Max production parity with K8s | Week 1 — too much complexity |
| **Nix/devenv** | Reproducible environments without containers | Most teams — niche skill |
| **Testcontainers** | Spinning up services inside tests | Running the full app |

**Decision for SmartCourse:** Docker Compose for running the stack + Testcontainers for the test suite.

---

### Q: How does Docker work?

**A:**

- **Image** — a read-only, layered snapshot of a filesystem (blueprint)
- **Container** — a running instance of an image; an isolated process, not a VM
- **Dockerfile** — instructions to build an image layer by layer
- **Volume** — persistent storage that survives container restarts
- **Network** — containers talk to each other by service name, not localhost
- **Docker Compose** — orchestrates multiple containers with one command

Each image layer is cached. Only changed layers rebuild — keeping builds fast.

---

### Q: What are the major cons of Docker?

**A:**

1. **Heavy on Mac/Windows** — Docker runs a Linux VM underneath. 4–8 GB RAM overhead just idle.
2. **Slow volume mounts on Mac** — file sync between Mac filesystem and VM causes 1–3s hot reload delays.
3. **Ephemeral by default** — `docker-compose down` without `-v` caution deletes your DB data.
4. **Image bloat** — images pile up fast. 15–30 GB disk after a few weeks. Run `docker system prune` regularly.
5. **Networking complexity at scale** — `depends_on` only waits for container start, not service readiness.
6. **Docker daemon runs as root** — security risk if misconfigured.
7. **Not production-representative** — Compose is a dev tool. Production uses Kubernetes, ECS, etc.
8. **Layer cache invalidation** — wrong Dockerfile order = full reinstall on every code change.

---

### Q: Why use Alpine images?

**A:**

Alpine Linux is a minimal OS — only ~5 MB base vs Ubuntu's ~80 MB.

- `postgres:15` = 375 MB → `postgres:15-alpine` = 80 MB
- Faster pulls, less disk, fewer pre-installed packages = fewer vulnerabilities
- Alpine is actually **more secure** than Ubuntu for infra containers

**Exception:** Don't use Alpine for your Python app container. Alpine uses `musl libc` instead of `glibc` — some Python packages fail to compile. Use `python:3.11-slim` (Debian-based, glibc-compatible) for the app.

**Rule:** Alpine for infra (Postgres, Redis, RabbitMQ). `slim` for Python app.

---

### Q: What is ZooKeeper and why did Kafka need it?

**A:**

Kafka is a cluster of broker nodes. Someone needs to answer:
- Which broker is the leader?
- Which brokers are alive?
- Which broker owns which partition?

ZooKeeper was a separate service Kafka relied on to answer these questions. Your stack was:

```
ZooKeeper (separate service) ← Kafka brokers ← Your app
```

**Problems:** Extra service to run, monitor, scale. Two systems to debug. Bottleneck at large scale.

---

### Q: What is KRaft mode?

**A:**

KRaft = Kafka Raft. Kafka's own built-in consensus protocol — replaces ZooKeeper entirely.

Kafka brokers now manage their own metadata using the Raft algorithm (same used in etcd, CockroachDB).

```
Before KRaft:               After KRaft:
ZooKeeper + Kafka (2 things) → Kafka only (1 thing)
```

In our compose file: `KAFKA_CFG_PROCESS_ROLES: broker,controller` — one process does both jobs.

**KRaft is responsible for:**
- Leader election (who's in charge if a broker crashes)
- Cluster membership (which brokers are alive)
- Topic/partition metadata (who owns what data)

Production-ready since Kafka 3.3. We use 3.6 — KRaft is the right default.

---

### Q: Where does ZooKeeper still matter?

**A:**

Still in use with:
- **Kafka < 3.3** — many companies haven't upgraded yet
- **Apache HBase** — big data storage, still ZooKeeper-dependent
- **Apache Hadoop** — legacy big data ecosystem
- **Enterprise legacy systems** — banks, telecoms running 2015–2019 stacks

If you join a company on Kafka 2.x, you'll see ZooKeeper. Not dead — just being phased out in new setups.

---

### Q: What is Bitnami? It wasn't in our guidelines — why use it?

**A:**

Bitnami (VMware/Broadcom) maintains well-configured Docker images for common open-source software.

**Why not the official Apache Kafka image:**
The official image requires manually writing `server.properties` config files and mounting them. Complex for no benefit.

**Bitnami Kafka:** Same Kafka software, configured via clean environment variables:
```yaml
KAFKA_CFG_PROCESS_ROLES: broker,controller
KAFKA_CFG_NODE_ID: 1
```

Same software, better packaging — like a phone with a case vs without.

**Tradeoff to be aware of:** Bitnami images sometimes lag a few days behind official releases. Not a concern for a dev environment.

If the mentor prefers the official image, we can switch — the compose config will just be longer.

---

### Q: How does Temporal + DB work? Is Temporal connected to the DB?

**A:**

Yes — Temporal stores **all its state in a database** (Postgres, MySQL, or Cassandra).

```
Your App
   │ gRPC
   ▼
Temporal Server ──── PostgreSQL
   │                 (stores: workflow state, history,
   │                  task queues, timers, signals)
   ▼
Your Worker Code
```

Temporal is a **durable execution engine**. Every workflow step is persisted to the DB. If the server crashes mid-workflow, it replays from DB on restart — that's how it guarantees completion.

**`temporalio/auto-setup` image:** Normally you'd run DB schema migrations manually before starting Temporal. `auto-setup` does this automatically on first start against your existing Postgres.

**Important:** Temporal does NOT touch your app's tables. It uses its own internal schema. Your users/courses/enrollments are completely separate.

---

### Q: What is Cassandra? How is it different from MySQL/Postgres?

**A:**

**Postgres = Excel spreadsheet**
- Rows and columns, fixed schema
- Tables JOIN together
- One main server
- Great for structured relational data

**Cassandra = a notebook spread across 10 buildings**
- Each building holds a copy of some pages
- No JOINs — look up by a specific key only
- Built from day one to scale across many machines
- Write-heavy workloads at massive scale

**Key difference in practice:**

```sql
-- Postgres: JOINs work
SELECT u.name, e.course_id FROM users u
JOIN enrollments e ON u.id = e.student_id WHERE u.id = 5

-- Cassandra: no JOINs — table is designed around one query pattern
SELECT * FROM enrollments_by_student WHERE student_id = 5
```

**When Cassandra wins:** Millions of writes per second, data spread across regions, simple key-based lookups.

**When Postgres wins:** Complex queries, JOINs, ACID transactions, structured relational data.

**For SmartCourse:** Postgres = source of truth (users, courses, enrollments). Cassandra/MongoDB = analytics and event data (write-heavy, simple lookups like lesson completion counts).

---

### Q: I prefer glibc over musl — what does that mean for the project?

**A:**

For the Python app container, use `python:3.11-slim` (Debian-based, glibc). Never use `python:3.11-alpine` (musl).

Alpine images are fine for infra services (Postgres, Redis, RabbitMQ) since those have tested Alpine builds. The app container must use slim/glibc to avoid package compilation failures.

---

### Q: Is Cassandra like sharding?

**A:**

Yes — but sharding is something you do **to** a database. Cassandra has it **built in by default**.

- **Postgres sharding:** You manually split data across servers. You manage the split, rebalancing, routing — painful and error-prone.
- **Cassandra:** Every row has a partition key. Cassandra automatically decides which node holds which partition. Add a node, data rebalances automatically.

```
Postgres sharding = you doing Cassandra's job manually
Cassandra = sharding is the default, built-in behavior
```

---

### Q: What does SmartCourse demand — SQL or Cassandra? Where does each fail?

**A:**

**Where PostgreSQL fails:**
- 500k+ writes per second — single node becomes a bottleneck
- Data spread across multiple regions — replication lag, split-brain
- Billions of rows — query performance degrades without heavy tuning
- Schema changes on huge tables — `ALTER TABLE` locks the table, causes downtime

**Where Cassandra fails:**
- JOINs — doesn't exist at all
- Complex filtering (`WHERE status = 'active' AND created_at > X`) — only works if those columns are in the partition key
- `SELECT COUNT(*)` — extremely slow
- Transactions across multiple rows — no ACID across partitions
- Unknown query patterns upfront — table design depends on knowing exactly how you'll query. Wrong design = rebuild everything
- Low volume apps — massive operational overhead for no benefit

**For SmartCourse specifically:**

Core data (users, courses, enrollments, progress) → **PostgreSQL only**. These are relational, need JOINs, need ACID transactions, need foreign keys. Cassandra can't do this cleanly.

Analytics (enrollments over time, completion rates, popular courses) → **PostgreSQL handles this fine** up to 50k concurrent users with proper indexes. Cassandra is only worth it at millions of events per second (Netflix-scale).

---

### Q: Do we need both Cassandra and MongoDB?

**A:**

No. The PRD says "MongoDB / Cassandra" — pick one, not both.

| | MongoDB | Cassandra |
|---|---|---|
| Data model | JSON documents, flexible schema | Wide-column, rigid partition key |
| Query flexibility | High — filter on any field | Low — must design around query |
| Write speed at scale | Good | Excellent |
| Operational complexity | Low–Medium | High |
| Good for | Semi-structured content, documents | Time-series, event logs, massive writes |
| Learning curve | Easy | Steep |

**Decision for SmartCourse:** Neither is needed in Weeks 1–3. PostgreSQL handles everything comfortably at this scale.

If one is added later, **MongoDB is the better fit** because:
- Course content (modules → lessons → chunks → text) is document-shaped — fits JSON naturally
- Flexible schema helps when content structure varies per course
- Integrates cleanly with the Part B embedding/RAG pipeline
- Much easier to operate than Cassandra

Cassandra would only make sense if analytics traffic hits a scale where Postgres read replicas aren't enough — a Week 3+ decision based on actual load, not upfront assumption.

---

### Q: What is GIN index?

**A:**

GIN = Generalized Inverted Index.

Normal B-tree index: one value → one row pointer.
GIN index: breaks content into tokens → maps each token to all matching rows.

```
GIN on title + description:
"python"   → rows 1, 5, 12
"basics"   → rows 5, 8
"learning" → rows 2, 7, 9, 12
```

When a student searches "python basics" — Postgres finds the intersection instantly. No table scan. Used for full-text search columns, JSONB columns, and array columns.

---

### Q: Is video streaming a requirement in the PRD?

**A:**

No. `content_type (video/text/pdf)` and `content_url` are from the Week 1 plan, not the PRD. The `content_url` is just a link to where a file is hosted (S3, CDN). SmartCourse stores the URL, not the video itself. No video infrastructure needed.

---

### Q: Do we need login/signup? The PRD doesn't mention it explicitly.

**A:**

Yes — it's implied everywhere. The PRD says "user registration with roles", "student enrollment", "instructors create courses". None of these work without knowing who is making the request.

Auth is foundational infrastructure. PRDs assume it exists without listing it.

Week 1 auth endpoints:
- `POST /api/v1/auth/register` — signup
- `POST /api/v1/auth/login` — returns JWT token
- `GET /api/v1/users/me` — who am I (reads JWT)

JWT token carries: `user_id`, `role`, `expires_at`. Every protected endpoint reads this from `Authorization: Bearer <token>` — no DB hit needed to identify the caller.

---

### Q: What is the difference between SQLAlchemy and psycopg (PostgreSQL driver)?

**A:**

They are different layers that work together — not alternatives.

```
FastAPI App → SQLAlchemy → psycopg → PostgreSQL
```

- **PostgreSQL** — the database server, stores data, understands SQL
- **psycopg** (psycopg2/psycopg3) — Python driver, connects to PostgreSQL, sends raw SQL strings
- **SQLAlchemy** — ORM, sits on top of psycopg, lets you use Python classes instead of writing raw SQL

SQLAlchemy does not replace psycopg. It uses psycopg underneath. You need both.

**Same query, three ways:**
```python
# Raw psycopg — get tuples back
cursor.execute("SELECT id, title FROM courses WHERE status = 'published'")

# SQLAlchemy ORM — get Python objects back
result = await db.execute(select(Course).where(Course.status == "published"))
courses = result.scalars().all()  # [<Course>, <Course>]
```

ORM advantages: SQL injection protection by default, Python objects not tuples, relationships work automatically (`course.modules`), refactoring changes one class not many SQL strings.

ORM disadvantages: complex aggregation queries are painful to write in ORM syntax, hides what SQL is generated (N+1 problem common for beginners), sometimes generates inefficient SQL.

Solution: use ORM for standard CRUD, drop to raw SQL for complex analytics queries via `db.execute(text("..."))`.

**Why psycopg3 (async) not psycopg2:**
psycopg2 is synchronous — blocks the FastAPI event loop while waiting for DB. psycopg3 is async — app handles other requests while waiting for DB response.

Stack used: `sqlalchemy[asyncio]` + `psycopg[async]` + `alembic` (reads SQLAlchemy models, generates migration files).

---

### Q: What is Mapped and mapped_column vs old Column()?

**A:**

SQLAlchemy 2.0 replaced `Column()` with `Mapped` + `mapped_column()` to add full Python type awareness.

Old style (don't use):
```python
id = Column(UUID, primary_key=True)         # no type info, no autocomplete
email = Column(String(255), nullable=False)
```

New style (what we use):
```python
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
email: Mapped[str] = mapped_column(String(255), nullable=False)
full_name: Mapped[str | None] = mapped_column(String(255))  # nullable
```

`Mapped[str]` = this attribute is always a string. Editor, mypy, and FastAPI all know this. Full autocomplete and type safety. `Mapped[str | None]` = nullable column.

---

### Q: What are SQLAlchemy dialects?

**A:**

Every database adds its own types on top of standard SQL. SQLAlchemy calls these extras "dialects."

```python
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
```

- `UUID` — PostgreSQL's native UUID type (16 bytes, stored efficiently, not as text)
- `TIMESTAMPTZ` — timestamp with timezone. Always stores in UTC, converts on read. Standard SQL `TIMESTAMP` has no timezone awareness.

`sqlalchemy` = generic SQL (works on any DB)
`sqlalchemy.dialects.postgresql` = Postgres-specific features

Using dialect types means Postgres stores data in its most efficient native format instead of falling back to text/varchar.

---

### Q: What do relationship() lines mean in SQLAlchemy models?

**A:**

Relationships let you navigate between connected tables in Python without writing JOINs manually.

```python
# In Certificate model:
enrollment: Mapped["Enrollment"] = relationship("Enrollment", back_populates="certificate")
student: Mapped["User"] = relationship("User")
course: Mapped["Course"] = relationship("Course", back_populates="certificates")
```

- `certificate.enrollment` → gives the full Enrollment object (SQLAlchemy runs the JOIN)
- `certificate.student` → gives the full User object
- `certificate.course` → gives the full Course object

`back_populates="certificate"` means the Enrollment model has a matching `enrollment.certificate` pointing back — linked both ways. Without `back_populates`, the relationship is one-directional.

Strings in quotes (`"Enrollment"`, `"User"`) = forward references to avoid circular imports at class definition time.

Practical effect:
```python
cert = await db.get(Certificate, cert_id)
print(cert.student.full_name)  # no manual JOIN needed
print(cert.course.title)
```

---

### Q: Where is it written that we need a separate analytics DB?

**A:**

Nowhere. That was an incorrect assumption. Neither the PRD nor the guidelines mention a separate analytics database.

Almost every analytics metric in the PRD comes from data already in the core Postgres tables:
- Total Students/Instructors → users table
- Total Courses Published → courses table
- Enrollments Over Time, Completion Rate, Avg Time to Complete, Most Popular Courses → enrollments table

No `analytics_events` table needed. No separate analytics DB. Query the existing tables directly.

"Failed Events / Workflow Issues" is the exception — it comes from Prometheus counters exposed by Celery workers, not from the DB at all.

---

### Q: Do observability tools (Prometheus, Grafana, Jaeger, OpenTelemetry) require schema changes?

**A:**

No. They operate completely outside your application database.

- **OpenTelemetry** — a library added to FastAPI. Wraps HTTP requests, DB queries, Kafka messages with trace context. Ships data elsewhere. No schema change.
- **Jaeger** — receives traces from OpenTelemetry, stores them in its own internal storage. You never write to Jaeger. No schema change.
- **Prometheus** — scrapes a `/metrics` endpoint your app exposes. Stores metrics in its own time-series DB. No schema change.
- **Grafana** — reads from Prometheus and Jaeger, draws dashboards. Touches nothing in your DB.

"Failed Events / Workflow Issues" metric = Prometheus counters incremented by Celery workers when tasks fail. Not stored in Postgres.

The only thing observability needs from your schema: timestamps on every table (created_at, updated_at, enrolled_at, completed_at) — which already exist.

**Final Week 1 schema — locked:**
users, courses, modules, lessons, enrollments, progress, certificates. Seven tables. Nothing else.

---

### Q: Why not put analytics in MongoDB instead of PostgreSQL?

> **⚠️ Partially superseded — 2026-05-14.** The conclusion *"analytics **metrics** → Postgres SQL"* still stands. But the closing line *"MongoDB's job is lesson_chunks"* does **not** — chunks moved to Postgres/pgvector and MongoDB's job became the raw interaction/event log. See **"Final storage architecture (resolved)"** at the end of this session log.

**A:**

MongoDB can handle analytics — but PostgreSQL wins for SmartCourse's specific metrics.

The PRD metrics are: counts, averages, group-bys, and JOINs between enrollments and courses. These are SQL-shaped problems.

| | PostgreSQL | MongoDB |
|---|---|---|
| COUNT, AVG, GROUP BY | Native clean SQL | Verbose aggregation pipeline |
| JOINs (course title + count) | Natural | `$lookup` — slow and awkward |
| Grafana integration | Native, first-class | Plugin required |
| Write speed | Good at our scale | Slightly faster, irrelevant |
| Schema flexibility | Fixed — fine for known metrics | Not needed for predictable metrics |

MongoDB wins for analytics only when: events have unpredictable shapes (flexible schema helps), or you're doing real-time stream processing. Neither applies here.

The data already lives in Postgres. The metrics are SQL problems. Grafana + Postgres is the standard pairing. No reason to move data to MongoDB just to query it differently.

MongoDB's job in this project is lesson_chunks storage — where it genuinely fits. Not analytics.

---

### Q: Why store analytics events in PostgreSQL? Is that in the PRD?

> **⚠️ Resolved — 2026-05-14.** This entry correctly deferred the storage decision; it has since been made. The granular **interaction/event log** lives in **MongoDB**; the **9 dashboard metrics** are SQL rollups in Postgres. See **"Final storage architecture (resolved)"** at the end of this session log.

**A:**

It is NOT explicitly in the PRD. The PRD lists analytics metrics that need to be computed but never specifies where to store them. Adding `analytics_events` to the Week 1 schema was an assumption — and a wrong one.

The PRD says: Week 3 — "Basic analytics metrics" + "Analytics pipeline initialized." That is when the analytics storage decision should be made, not Week 1.

Options for analytics storage (Week 3 decision):
- **PostgreSQL** — simple, aggregation queries easy (GROUP BY, COUNT, AVG). Risk: analytics writes competing with core data writes on same DB.
- **Redis** — blazing fast counters (INCR, ZADD). Not good for complex queries like avg completion time.
- **Kafka → sink** — events flow through Kafka, consumer writes to separate store. Decoupled but more infra.
- **Separate Postgres DB** — protects core DB from analytics load.

For SmartCourse's scale, Postgres is likely fine — but as a separate schema, decided in Week 3.

**Week 1 schema — final and clean:**
users, courses, modules, lessons, enrollments, progress, certificates. Nothing else.

---

### Q: What is the full Part A picture across all 3 weeks?

**A:**

**Week 1 — Identity + Course Structure**
Users, auth, JWT, roles, courses, modules, lessons CRUD. Foundation everything else sits on.

**Week 2 — The Two Core Workflows**

Enrollment workflow (synchronous + async):
```
POST /enroll →
  Postgres transaction: record enrollment + initialize progress  (sync, ACID)
  Kafka event: user.enrolled →
    Celery: update analytics counters  (async)
    Celery: send welcome notification  (async)
```

Publishing workflow (Temporal):
```
PATCH /courses/:id/publish →
  Set status = "processing"  (sync)
  Temporal workflow:
    Extract content chunks from lessons
    Store chunks for search
    Mark status = "published" only after all steps complete
    If any step fails → retry that step, not the whole workflow
```

Partial failures must not corrupt publishing — that's exactly what Temporal solves.

**Week 3 — Events + Workers + Observability**

Kafka events: `user.enrolled`, `course.published`, `lesson.completed`
Celery workers consume events: update analytics, send notifications, process content
Observability: OpenTelemetry → Jaeger (tracing), Prometheus → Grafana (metrics)
Failed events are surfaced as a dashboard metric, not just logged.

**One schema addition needed for full Part A:**

`analytics_events` table (event_type, user_id, course_id, occurred_at, metadata JSONB) — append-only event log, aggregated for dashboard metrics.

`content_chunks` does NOT belong in Postgres — that's MongoDB territory in Week 4.

---

### Q: What is the course hierarchy? What are modules and lessons?

**A:**

```
Course       → what a student enrolls in ("Complete Python Bootcamp")
  Module     → a logical chapter/section ("Week 1: Basics")
    Lesson   → individual learning unit ("Variables and Data Types")
               content_url → link to actual file on S3/CDN
```

A student completes lessons. All lessons done → enrollment complete → certificate issued.

---

### Q: Are chunks and embeddings the same thing? Where do they live?

> **⚠️ Superseded — 2026-05-14.** Chunks and embeddings are still separate *concepts*, but they no longer live in MongoDB — both moved to **Postgres + pgvector** (a chunk and its embedding are one row). See **"Final storage architecture (resolved)"** at the end of this session log.

**A:**

They are separate concepts and both belong in MongoDB (Week 4), not PostgreSQL.

**Lesson (Postgres, Week 1):** metadata — title, type, URL, order index.

**Chunk (MongoDB, Week 4):** the actual text of a lesson broken into smaller pieces (300–400 words each) for semantic search. One lesson = multiple chunks.

**Embedding (MongoDB/Vector DB, Week 4):** a numerical vector (array of ~1536 floats) representing a chunk's meaning. Used for similarity search in the RAG pipeline.

```
Postgres:  lessons row → { title: "Functions", content_url: "s3://..." }

MongoDB:   { lesson_id: "same-uuid", chunk_index: 0,
             text: "A function is a reusable block...",
             embedding: [0.023, -0.841, ...] }
```

The `lesson_id` in MongoDB references the Postgres lesson — that's the bridge between systems.

**Corrected schema ownership:**
- PostgreSQL: users, courses, modules, lessons, enrollments, progress, certificates, analytics_events
- MongoDB: lesson_chunks — raw text in Week 2, embeddings added in Week 4

---

### Q: Where does content get stored during the publishing workflow (Week 2)?

> **⚠️ Superseded — 2026-05-14.** The workflow steps are still right, but the storage target changed: raw chunks are written to **Postgres** (alongside their embeddings via pgvector), **not** MongoDB. MongoDB instead receives the interaction/event log. See **"Final storage architecture (resolved)"** at the end of this session log.

**A:**

The publishing workflow (Temporal, Week 2) does:
1. Validate course has modules + lessons
2. Extract text from lesson files (content_url points to file on S3/CDN)
3. Break text into chunks (~300 words each)
4. Store raw chunks in MongoDB
5. Mark course status = "published"

Storage split:
- Course status transitions → PostgreSQL
- Raw text chunks → MongoDB (Week 2, no embeddings yet)
- Embeddings added to same MongoDB documents → Week 4

MongoDB document lifecycle:
```
Week 2: { lesson_id, course_id, chunk_index, text, created_at }
Week 4: { lesson_id, course_id, chunk_index, text, created_at, embedding: [...] }
```

Same document, embedding field added later. No migration needed.

Why NOT PostgreSQL for chunks: chunks are unstructured text with no relational queries needed. MongoDB's document model fits naturally. Embeddings (1536-float arrays) are also better stored in MongoDB/vector DB than Postgres.

Why NOT defer chunking to Part B: PRD explicitly says chunking is part of the publishing workflow — "broken into components (modules, lessons, chunks)." Skipping it in Part A makes the publishing workflow incomplete.

Week-by-week storage:
| Week | Storage |
|---|---|
| Week 1 | PostgreSQL only |
| Week 2 | PostgreSQL (status, enrollments) + MongoDB (raw chunks) |
| Week 3 | PostgreSQL (analytics_events) |
| Week 4 | MongoDB (embeddings added to chunks) |
| Week 5 | MongoDB vector search for RAG |

---

### Q: What happens if we put core data in Cassandra and analytics in Postgres (reversed)?

**A:**

Both sides break simultaneously.

**Core data in Cassandra breaks because:**
- No UNIQUE constraints across partitions — duplicate enrollments possible under concurrent load
- No multi-row transactions — enrolling a student (write enrollment + initialize progress + update counter) can partially fail with no rollback
- Complex queries don't work unless you designed the table around that exact query upfront — wrong design means full table scan across all nodes

**Analytics in Postgres breaks because:**
- Analytics is write-heavy — millions of tiny inserts (lesson completed, page viewed, video paused) constantly
- Postgres VACUUM can't keep up at that volume — dead rows pile up, indexes bloat, writes slow down
- This slows your core DB too since they share infrastructure

The reversal takes away Postgres's strengths (transactions, flexible queries) and Cassandra's strengths (write throughput) at the same time.

---

### Q: Why does analytics need Cassandra? What's the real reason?

**A:**

Analytics data follows one pattern: write once, never update, read later in bulk.

Every event (lesson completed, page viewed) = one tiny write. At scale = millions of writes per second, constantly, forever.

**Why this kills Postgres:** Every Postgres write acquires locks, updates WAL, updates indexes, and eventually needs VACUUM to clean dead rows. Under millions of writes/second, VACUUM can't keep up, indexes bloat, locks pile up. The whole DB slows — including your core user/course queries.

**Why Cassandra handles it:** Cassandra uses an LSM Tree (Log-Structured Merge Tree). Writes go to an in-memory buffer, then flush to disk in batches. No locks, no VACUUM, no index contention. It handles massive write volume with barely any slowdown.

The tradeoff: Cassandra pays for fast writes by making reads harder. Complex queries and aggregations are painful. That's fine for analytics — you mostly ask simple questions like "how many completions today?", not complex JOINs.

Note: At SmartCourse's scale (tens of thousands of users), Postgres with proper indexes handles analytics fine. Cassandra is only worth it at 10M+ events/day.

---

### Q: What is the origin of Cassandra?

**A:**

Built at **Facebook in 2008** for inbox search. The problem: hundreds of millions of messages written daily — Postgres and MySQL couldn't handle the write volume.

Engineers combined two existing ideas:
- **Amazon Dynamo (2007)** — distributed key-value store, great for writes and availability
- **Google Bigtable (2006)** — wide-column storage, great for structured data at scale

They took Dynamo's distribution model + Bigtable's data model = Cassandra.

Open-sourced by Facebook in 2008. Apache took it over in 2010.

The name is from Greek mythology — Cassandra was the prophet who was always right but never believed. The engineers felt the same about their internal design decisions being dismissed.

**Key insight from origin:** Cassandra was built to solve ONE problem — massive write throughput across many machines with no downtime. JOINs don't exist because they'd require cross-node coordination, killing write speed. Everything about Cassandra flows from that original constraint.

---

### Q: Full comparison — MongoDB vs Cassandra vs PostgreSQL?

**A:**

**Storing the same data (course + modules + lessons):**

PostgreSQL: three tables linked by foreign keys, queried with JOINs.

MongoDB: one JSON document with modules and lessons nested inside. No JOINs needed.

Cassandra: a flat table designed around one specific query ("give me all lessons for course X"). Ask anything else — you need a new table.

| | PostgreSQL | MongoDB | Cassandra |
|---|---|---|---|
| Data model | Tables + rows | JSON documents | Wide-column rows |
| Schema | Strict | Flexible | Strict partition key |
| JOINs | Yes | No (embed instead) | No |
| Transactions | Full ACID | Single-document ACID | Limited |
| Write speed | Good | Good | Excellent |
| Read flexibility | Excellent | Good | Low — must match partition key |
| Scale model | Vertical + read replicas | Horizontal sharding | Horizontal, automatic |
| Best for | Relational, transactional data | Documents, content, catalogs | Time-series, events, massive writes |
| Operational complexity | Low | Low–Medium | High |

**Where each truly fails:**

PostgreSQL fails at: 1M+ writes/second, no natural relational structure, global multi-region writes.

MongoDB fails at: strict multi-document consistency, deeply relational data, extreme write volume.

Cassandra fails at: unknown query patterns upfront (wrong partition key = rebuild everything), aggregations (SUM/AVG/GROUP BY), small teams (high operational overhead), modest data volume.

**SmartCourse decision:**
- PostgreSQL → users, courses, modules, lessons, enrollments, progress
- MongoDB → course content documents, chunked lesson text (Week 4, feeds RAG pipeline)
- Cassandra → not needed at this scale
- Redis → caching, session data, Celery results

---

## Session 2 — 2026-05-08

---

### Q: Why do we need sessions for connecting to the database? Why not just use connections directly?

**A:**

A connection and a session are two different things.

**Connection** = the physical pipe between Python and PostgreSQL. TCP socket, authenticated, expensive to create (~50ms).

**Session** = a unit of work on top of a connection. Tracks what you've read, what you've changed, manages the transaction.

```
Connection = a phone line (the physical wire)
Session    = one phone call on that line (a conversation with a purpose)
```

Without a session, if you insert a user then fail inserting the enrollment, the user row stays — data is corrupted. The session gives you transactions — all-or-nothing. If anything fails, rollback() undoes everything cleanly.

In Node.js, transaction objects in libraries like Sequelize/Prisma serve the same purpose as SQLAlchemy sessions.

---

### Q: Why pool_size=10? Code without it — does that mean no pool?

**A:**

No — when you don't specify pool_size, SQLAlchemy defaults to pool_size=5, max_overflow=10. There is always a pool, just with default values. Specifying it explicitly makes the behaviour intentional and visible.

Without a pool: every request opens a new connection (50ms overhead) → closes it. Under load this is catastrophic.

With pool_size=10: 10 connections pre-opened at startup, reused across requests. Zero connection overhead per request.

pool_size=10 is conservative and safe for a single-worker dev setup. With multiple Uvicorn workers (e.g. 4), total connections = 4 × 10 = 40. Tune based on PostgreSQL's max_connections (default 100).

---

### Q: How does async work with the database? How does it relate to Uvicorn?

**A:**

Python runs on one thread with an event loop. The event loop manages multiple tasks — when one task is waiting (for DB response, network), it steps aside and another task runs.

**Sync DB (blocks everything):**
```
Request A → send query → WAITING (thread frozen) → no other requests served
```

**Async DB (asyncpg + AsyncSession):**
```
Request A → send query → "I'm waiting, event loop take over"
    Request B starts → sends its query → "I'm waiting too"
    Request C starts → sends its query → "I'm waiting too"
    DB responds to A → resume A → respond
    DB responds to B → resume B → respond
```

The `await` keyword is what yields control back to the event loop while waiting for PostgreSQL.

**Uvicorn** is the ASGI server that runs FastAPI and manages the event loop. FastAPI is just a framework — it needs Uvicorn to actually receive HTTP connections. You start it with `uvicorn app.main:app`. By default: 1 worker, 1 event loop.

```
Browser → HTTP → Uvicorn (manages event loop) → FastAPI (routing) → your route → SQLAlchemy → asyncpg → PostgreSQL
```

---

### Q: What is the difference between Python async and Node.js async?

**A:**

Both use a single-threaded event loop — architecturally very similar.

| | Node.js | Python FastAPI + Uvicorn |
|---|---|---|
| Default behavior | Async everywhere by default | Sync by default, async is opt-in |
| Event loop | libuv (C++) | asyncio (Python) |
| DB driver | pg, mysql2 (async native) | asyncpg (async native) |
| Server | Node IS the server | Uvicorn runs FastAPI |
| Blocking risk | Hard — must use *Sync methods deliberately | Easy — accidentally call any sync library and block |

Biggest risk in Python that doesn't exist in Node: accidentally calling sync code inside an async route blocks the entire event loop.

---

### Q: Examples of sync code accidentally blocking the async event loop?

**A:**

**time.sleep vs asyncio.sleep:**
```python
# WRONG — freezes event loop for 2s, no other requests served
time.sleep(2)

# RIGHT — yields control, other requests run during wait
await asyncio.sleep(2)
```

**HTTP calls:**
```python
# WRONG — requests library is sync, blocks
import requests
response = requests.get("https://api.example.com")

# RIGHT — httpx with async client, yields
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get("https://api.example.com")
```

**Database:**
```python
# WRONG — sync SQLAlchemy session, blocks event loop
users = db.query(User).all()

# RIGHT — async session, yields while waiting for PostgreSQL
result = await db.execute(select(User))
```

**Password hashing (CPU-intensive):**
```python
# WRONG — bcrypt takes ~100ms on main thread, blocks event loop
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

# RIGHT — run in thread pool, frees the event loop
loop = asyncio.get_event_loop()
hashed = await loop.run_in_executor(None, partial(bcrypt.hashpw, password.encode(), bcrypt.gensalt()))
```

**Effect of blocking:**
```
10 requests arrive, request 1 hits time.sleep(2)
→ all 10 wait behind it → total time: 20 seconds

10 requests arrive, request 1 hits await asyncio.sleep(2)
→ all 10 run in parallel → total time: ~2 seconds
```

In Node.js, sync blocking requires deliberate effort (fs.readFileSync, execSync). In Python, sync is the default — easy to accidentally block.

---

### Q: What is Gunicorn and how does it relate to Uvicorn in production?

**A:**

In development you run `uvicorn app.main:app --reload` — one process, one event loop.

In production:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

- **Gunicorn** = process manager. Spawns and manages N worker processes. Handles crashes, restarts workers.
- **Uvicorn** = ASGI server inside each worker. Runs the event loop and handles async requests.

```
Client
  └── Gunicorn (process manager)
        ├── Worker 1 → Uvicorn → Event Loop → FastAPI → coroutines
        ├── Worker 2 → Uvicorn → Event Loop → FastAPI → coroutines
        ├── Worker 3 → Uvicorn → Event Loop → FastAPI → coroutines
        └── Worker 4 → Uvicorn → Event Loop → FastAPI → coroutines
```

4 workers × pool_size 10 = 40 total PostgreSQL connections. Set pool_size accordingly.

---

### Q: What is MVCC and how is it different from locks?

**A:**

**Traditional locks:** a writer locks a row → readers must wait. Poor concurrency under load.

**MVCC (Multi-Version Concurrency Control)** — PostgreSQL's approach:
- Every row update creates a new version of the row, not an overwrite
- Readers see the old version while writers are writing the new version
- Readers and writers never block each other

```
Transaction A (reading):  sees version 1 of the row
Transaction B (writing):  creates version 2 of the row simultaneously
No blocking — both proceed at the same time
```

MVCC is why PostgreSQL handles high concurrency well. The tradeoff: dead row versions accumulate and VACUUM must clean them up periodically.

---

### Q: What is WAL (Write Ahead Log) in PostgreSQL?

**A:**

WAL = Write Ahead Log. Before PostgreSQL writes data to the actual table files, it writes the change to a sequential log first.

Why: if the server crashes mid-write, the actual table files may be partially written (corrupted). On restart, PostgreSQL replays the WAL to restore consistency — data is never lost.

```
Transaction:
  1. Write change to WAL (sequential, fast)
  2. COMMIT confirmed to application
  3. Later: apply change to actual table files (background)
```

Sequential writes to WAL are fast (disks are fast at sequential I/O). Table file writes are random I/O (slower) — WAL lets you confirm the transaction before that slow step.

WAL also enables replication — replicas stream and replay the primary's WAL.

---

### Q: What is the Saga / Compensation pattern? How does it apply to SmartCourse?

**A:**

When a workflow has multiple steps and one fails mid-way, you need to undo the steps that already succeeded. This is compensation.

```
Publishing workflow:
Step 1: save course       → success
Step 2: process lessons   → success
Step 3: generate chunks   → FAILS

Compensation (run in reverse):
Undo Step 2: delete processed lesson data
Undo Step 1: revert course to draft
```

Without compensation: course is stuck in a corrupted "partially published" state.

Temporal supports this natively — each workflow step can define a compensation handler. Celery requires you to build this manually, which is error-prone.

This is why the publishing workflow uses Temporal (Week 2) while simple background tasks like analytics updates use Celery.

---

### Q: Kafka vs Celery — what is the real difference?

**A:**

They solve different problems and complement each other.

**Celery** — executes a task. One producer, one consumer. Task runs once.
```
FastAPI → Celery → "send welcome email to user 5" → email sent
```

**Kafka** — broadcasts an event. One producer, many consumers. Event persists and is replayable.
```
FastAPI → Kafka: "user.enrolled" event
  → Consumer 1 (analytics worker): update enrollment count
  → Consumer 2 (notification worker): send welcome email
  → Consumer 3 (recommendation worker): update recommendations
```

| | Celery | Kafka |
|---|---|---|
| Consumers | One per task | Many independent consumers |
| Storage | Temporary (task gone after execution) | Persistent (events stored, replayable) |
| Use case | Execute a job | Broadcast what happened |
| Example | Send email | user.enrolled event |

In SmartCourse: Kafka fires `user.enrolled` → Celery workers consume it to send email and update analytics. They work together.

---

### Q: What is database replication and when would SmartCourse use it?

**A:**

Replication = one primary DB (handles writes) + one or more replica DBs (handle reads).

```
Primary DB  ← all writes (INSERT, UPDATE, DELETE)
     │
     └── streams WAL
           │
     Replica DB ← all reads (SELECT)
```

Benefit: distribute read load. Analytics queries (heavy SELECTs) go to replica, enrollment writes go to primary.

Tradeoff: replication lag — replica is slightly behind primary (milliseconds to seconds). For critical reads (e.g. "is this user enrolled?") — always read from primary. For analytics (slightly stale data is fine) — read from replica.

SmartCourse at tens of thousands of users: one primary is fine. Add a replica when read queries start slowing down writes.

---

### Q: What are the common production failure patterns to watch for?

**A:**

| Failure | Symptom | Fix |
|---|---|---|
| Slow queries | API response time spikes | Add missing index, run EXPLAIN ANALYZE |
| Lock contention | Requests queue up | Reduce transaction size, avoid long transactions |
| Deadlocks | Transactions failing randomly | Acquire locks in consistent order |
| Connection exhaustion | "too many connections" error | Tune pool_size, fix connection leaks |
| Replication lag | Stale reads on replica | Read from primary for critical data |
| Write bottleneck | Writes backing up | Buffer through Kafka, batch in Celery |
| N+1 queries | DB hit once per row in a loop | Use selectinload/joinedload eagerly |
| Blocking event loop | All requests slow simultaneously | Move sync/CPU code out of async routes |

---

### Q: What is the GIL and how does it affect SmartCourse?

**A:**

GIL = Global Interpreter Lock. A mutex in CPython that allows only one thread to execute Python bytecode at a time.

Impact:
- **Async I/O** — not affected. When a coroutine awaits (DB, network), it releases the GIL and another task runs. Async works fine.
- **CPU-bound threads** — blocked by GIL. Two Python threads cannot compute in parallel. One runs, one waits.

For SmartCourse:
- API request handling (I/O bound) → async works perfectly, GIL not a problem
- bcrypt hashing (CPU bound in one thread) → use `run_in_executor` to move to thread pool (GIL is released during C-extension work in bcrypt)
- Heavy ML inference in future (Part B) → use Celery worker (separate process, separate GIL)

Multiprocessing (Gunicorn workers) bypasses GIL entirely — each process has its own GIL and its own Python interpreter.

---

### Q: How does FastAPI dependency injection work? What is Depends()?

**A:**

Normally you call a function yourself: `result = my_function(arg)`. With `Depends()`, FastAPI calls it for you before your route runs and injects the result.

```python
@router.get("/courses")
async def list_courses(db: DBSession):  # FastAPI called get_db() and injected db
    ...
```

You declare what you need. FastAPI figures out how to provide it. This is Dependency Injection.

---

### Q: What does OAuth2PasswordBearer do in dependencies.py?

**A:**

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
```

It's a dependency that reads the `Authorization: Bearer <token>` header, strips the `Bearer ` prefix, and returns the token string. If the header is missing → raises 401 automatically before your code runs.

`tokenUrl` only tells Swagger UI (`/docs`) where the login endpoint is so the "Authorize" button works. It has nothing to do with actual token validation.

---

### Q: What is the three-layer auth chain in dependencies.py?

**A:**

```
Request
  ├── oauth2_scheme: Authorization header present?        → 401 if not
  ├── jwt.decode: signature valid? not expired?           → 401 if not
  ├── DB query: user still exists?                        → 401 if not
  ├── is_active check: account enabled?                   → 403 if not
  └── role check: right role for this endpoint?           → 403 if not
  ▼
Route handler runs (user is guaranteed valid, active, authorized)
```

401 = unauthenticated (we don't know who you are)
403 = unauthorized (we know who you are, but you can't do this)

Why same error message for all 401 cases: never tell an attacker whether the token was expired, tampered, or the user doesn't exist.

Why fetch user from DB even after validating JWT: token could be valid but user was deleted after issuance. Also need the full User object (role, is_active, id) for the route anyway.

---

### Q: What is the require_role dependency factory pattern?

**A:**

A function that returns a function. The inner function is the actual FastAPI dependency.

```python
def require_role(*roles: UserRole):
    async def role_checker(current_user: Depends(get_current_active_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return current_user
    return role_checker
```

Without factory: need a new function for every role combination (require_instructor, require_admin, require_instructor_or_admin...).
With factory: any combination with one function:
```python
require_role(UserRole.instructor)
require_role(UserRole.admin)
require_role(UserRole.instructor, UserRole.admin)
```

---

### Q: What are the type aliases in dependencies.py and why use them?

**A:**

```python
DBSession      = Annotated[AsyncSession, Depends(get_db)]
CurrentUser    = Annotated[User, Depends(get_current_active_user)]
InstructorUser = Annotated[User, Depends(require_role(UserRole.instructor, UserRole.admin))]
AdminUser      = Annotated[User, Depends(require_role(UserRole.admin))]
```

`Annotated[Type, metadata]` — Python's way of attaching extra info to a type hint. FastAPI reads the `Depends(...)` part as a dependency instruction.

Without aliases, every route signature is verbose:
```python
async def create_course(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.instructor))],
):
```

With aliases:
```python
async def create_course(db: DBSession, current_user: InstructorUser):
```

Same behaviour, same security enforcement, much cleaner. Import from `app.dependencies` in any router.

---

### Q: How is FastAPI Dependency Injection different from Node.js? How does it compare to Angular?

**A:**

**Node.js / Express — no DI, manual everything:**
```javascript
app.get('/courses', async (req, res) => {
    const db = req.db       // manually attached in middleware
    const user = req.user   // manually attached by auth middleware
    if (user.role !== 'instructor') return res.status(403).json(...)
    ...
})
```
No injection — you import, instantiate, and pass everything manually.

**Angular — constructor injection:**
```typescript
@Injectable({ providedIn: 'root' })
export class CourseService {
    constructor(private http: HttpClient, private authService: AuthService) {}
}
```
Angular's injector reads constructor types, creates instances, injects them.

**FastAPI — function parameter injection (same concept, different form):**
```python
async def create_course(db: Annotated[AsyncSession, Depends(get_db)]):
    # FastAPI called get_db() and injected the result as db
    # you never wrote: db = get_db()
```

Mental model:
```
Angular:  injector reads constructor types → creates & injects instances
FastAPI:  reads function params with Depends() → calls & injects results
```

DI solves: auth checks copy-pasted everywhere, db passed through every layer manually, tests requiring complex req/res mocking.

---

### Q: How is role access control maintained across the system? Where does it live?

**A:**

Two separate concerns — router and service layer:

**Router — role-based (who are you?):**
```python
@router.get("/courses")      # public — no auth
async def list_courses(db: DBSession): ...

@router.post("/courses")     # instructor or admin only
async def create_course(db: DBSession, user: InstructorUser): ...

@router.delete("/courses/{id}")  # admin only
async def delete_course(db: DBSession, user: AdminUser): ...
```

Reading the router file shows the entire access control policy at a glance.

**Service layer — ownership-based (is this yours?):**
```python
async def update_course(db, current_user, course_id, data):
    course = await course_repo.get_by_id(db, course_id)
    # role already checked by router dependency
    # ownership checked here
    if course.instructor_id != current_user.id and current_user.role != admin:
        raise HTTPException(403, "You don't own this course")
```

Role check = are you the right type of user? (router)
Ownership check = is this resource yours? (service)

---

### Q: Can Swagger handle security roles? What is it actually responsible for?

**A:**

Swagger shows security information (lock icons on protected endpoints) but cannot enforce roles.

What Swagger CAN do:
- Show which endpoints require authentication (lock icon)
- Show what auth scheme is needed (Bearer token)
- Provide a login form (via tokenUrl) to get a token for testing
- Show description text about required roles if you add it manually

What Swagger CANNOT do:
- Check what role a token belongs to
- Block requests based on role
- Enforce any business rules

```
Swagger shows:  POST /courses 🔔  ← "needs auth" (that's all it knows)
Server enforces: token valid? → user active? → role = instructor? → proceed
```

Think of it like Express: the API spec (Swagger) describes what should happen, the middleware (require_role) actually enforces it. Swagger is documentation + testing UI. require_role is real server-side enforcement that runs on every request and cannot be bypassed.

---

### Q: How does FastAPI avoid passing db everywhere compared to Express? When does dependencies.py actually run?

**A:**

**Express approaches to avoid manual db passing:**
```javascript
// Pattern 1: middleware attaches to req
app.use(async (req, res, next) => { req.db = await pool.getConnection(); next() })

// Pattern 2: module-level singleton (most common)
const db = require('./db')  // same instance imported everywhere
```

Problem with Express: auth checks are copy-pasted in every route. Forget once = security hole.

**FastAPI approach — declared in signature, injected automatically:**
```python
@router.post("/courses")
async def create_course(db: DBSession, user: InstructorUser):
    # db injected, auth done, role checked — zero boilerplate inside route
```

**dependencies.py — mechanism vs policy:**
- `dependencies.py` = defines HOW to check roles (the tools)
- `routers/*.py` = declares WHICH role is needed per route (the policy)

**When does it run — only what each route declares:**
```
GET /courses   → no dependencies declared → nothing from dependencies.py runs
GET /courses/1 → DBSession declared → only get_db() runs
POST /courses  → DBSession + InstructorUser → full chain runs:
                 oauth2_scheme → jwt.decode → DB query → is_active → role check
```

FastAPI reads each route's signature and only runs declared dependencies. Unlike Express `app.use()` which runs globally for all routes (requiring manual exclusions for public endpoints), FastAPI dependencies are per-route and precise.

---

## Session 3 — 2026-05-13

---

### Q: In `lock_course_for_enrollment` we call `.with_for_update()` — how is this a transaction, how does the lock work, and is it Postgres-specific?

**A:**

**Where the transaction comes from.** The function never calls `db.begin()`, yet a transaction exists. SQLAlchemy's `AsyncSession` uses **implicit/lazy transactions** — the first statement on a fresh session automatically issues `BEGIN`. The transaction stays open until `commit()` or `rollback()`. The session-per-request pattern in `app/database.py` then commits when the route handler returns successfully, or rolls back on exception:

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()        # <-- releases the FOR UPDATE lock
        except Exception:
            await session.rollback()      # <-- also releases it
            raise
```

So the flow during an enroll is:
```
1st query (lock_course_for_enrollment)  -> implicit BEGIN, row lock acquired
count_active(...)                       -> same txn, lock still held
enrollment_repo.create(...)             -> same txn
handler returns                         -> get_db() commits -> lock released
```

**What `.with_for_update()` emits.** On PostgreSQL it compiles to:
```sql
SELECT courses.* FROM courses WHERE courses.id = $1 FOR UPDATE
```
`FOR UPDATE` is standard SQL (SQL:1992) and works on Postgres / MySQL InnoDB / Oracle, but with **different semantics on each engine**. We're targeting Postgres.

**The lock mechanism (Postgres-specific details).** This is a **row-level exclusive lock**:
- Postgres marks the locked row by writing the locker's transaction ID into the tuple's hidden `xmax` field.
- Other transactions doing `UPDATE`, `DELETE`, `SELECT FOR UPDATE`, or `SELECT FOR NO KEY UPDATE` on the **same row** block waiting for us.
- Plain `SELECT` (no `FOR UPDATE`) is **not** blocked — Postgres MVCC lets readers see the previous committed version. Read traffic is unaffected.
- Lock is released automatically on `COMMIT` / `ROLLBACK`. No `UNLOCK` exists.

Postgres has a family of row-level locks; we picked the strongest:

| Mode | What it blocks on the same row | When to use |
|---|---|---|
| `FOR UPDATE` (chosen) | other FOR UPDATE / FOR NO KEY UPDATE / FOR SHARE / FOR KEY SHARE / UPDATE / DELETE | strict mutual exclusion |
| `FOR NO KEY UPDATE` | same, but doesn't conflict with FK checks | non-key column updates with better FK concurrency |
| `FOR SHARE` | UPDATE / DELETE / FOR UPDATE — but multiple FOR SHARE can co-hold | "read and freeze, but other readers welcome" |
| `FOR KEY SHARE` | only key-changing UPDATEs and DELETE | weakest; used internally by FK validation |

We use `FOR UPDATE` because anything weaker (e.g. `FOR SHARE`) would let two transactions both pass the capacity check.

**Why the lock is necessary — the race.** Classic read-modify-write race on the capacity check. With `max_students=50` and current count=49:
```
T1: SELECT count(*) ... -> 49
T2: SELECT count(*) ... -> 49        (both see same snapshot)
T1: 49 < 50, INSERT, COMMIT          -> count is now 50
T2: 49 < 50, INSERT, COMMIT          -> count is now 51   BUG (cap violated)
```
With `FOR UPDATE` on the courses row:
```
T1: SELECT * FROM courses WHERE id=X FOR UPDATE -> lock acquired
T2: SELECT * FROM courses WHERE id=X FOR UPDATE -> blocks waiting on T1
T1: count=49, INSERT, COMMIT                     -> lock released
T2: unblocks, count=50, full -> CourseFullError  -> 409
```

**Parent-row-as-gate pattern.** Note that we lock the **courses row** (parent), not the enrollments rows (children). We use the parent row as a mutex for any operation needing a consistent count of its children. Works because:
- `courses.id` is a stable single-row target — cheap.
- Every enrollment for that course funnels through the same lock.
- Plain reads on the course row aren't blocked, so this doesn't hurt read traffic.

**Deadlock note.** Postgres detects deadlocks automatically (`deadlock_timeout`, default 1s) and kills one victim. Our flow only locks one course row per request — no deadlock risk. If we ever lock two course rows in one transaction (e.g. "transfer enrollment between courses"), acquire them in canonical order (e.g. UUID ascending) to prevent A→B / B→A cycles.

**Alternatives we didn't pick:**

| Approach | Why not |
|---|---|
| Advisory locks (`pg_advisory_xact_lock`) | Faster but app-specific labels, less natural visibility in `pg_locks` |
| Optimistic concurrency (version column + retry) | Adds retry loop in app code; more failure modes; overkill at current scale |
| Denormalized `active_count` column with `UPDATE ... WHERE active_count < max RETURNING` | Single atomic statement, but adds a counter to maintain on every insert/delete/status change |
| Serializable isolation level | Too coarse — lots of `SerializationFailure` retries under contention |

`FOR UPDATE` is the sweet spot at current scale: correct, idiomatic, uses the DB the way it was designed.

---

### Q: Will transactions also be used in the analytics part (Week 3)?

**A:** Yes — but in a fundamentally different way. The analytics layer's transactions are separate, smaller, and decoupled from the original business transaction. This split is intentional.

**Two worlds of transactions in this system:**

| World | Why it uses a transaction | Example |
|---|---|---|
| Write path (enrollment, publish) | Atomicity + locking for races | `BEGIN -> FOR UPDATE -> check -> INSERT -> COMMIT` |
| Analytics writes (Celery consumer) | Idempotency + atomic counter update | `BEGIN -> mark event processed -> UPDATE counter -> COMMIT` |
| Analytics reads (dashboard query) | Consistency-of-snapshot (Postgres MVCC) | Single `SELECT` — implicit txn, no lock needed |

**Why analytics doesn't share the enrollment transaction (the "fat transaction" anti-pattern):**

```
BEGIN
  INSERT enrollment
  UPDATE course_stats SET enrolled_count = enrolled_count + 1   -- analytics
  UPDATE student_stats SET courses_count = courses_count + 1    -- analytics
  INSERT analytics_event (...)                                  -- analytics
COMMIT
```

Problems:
1. The `FOR UPDATE` lock on `courses` is held longer -> fewer concurrent enrolls possible (lock contention).
2. An analytics-side failure (constraint mismatch on a stat table) kills the user's enrollment with a 500 — for a reporting bug.
3. Analytics tables become hot — every enrollment serializes through them too.
4. Analytics can't scale independently — stuck in the same Postgres write path as enrollments.

**The async split (Week 3 pattern):**

```
TXN 1 (sync, fast, locks):
  INSERT enrollment
  COMMIT
  -> emit Kafka event "user.enrolled"

TXN 2 (async, in Celery worker, ms later):
  BEGIN
    mark event processed (idempotency)
    UPDATE course_stats SET enrolled_count = enrolled_count + 1
  COMMIT
```

The user's enrollment is durable in milliseconds. If analytics is slow or broken, the user never knows.

**Three transaction patterns Week 3 will use:**

**1. Transactional outbox** — solves "what if Kafka emit fails after commit?":
```sql
BEGIN;
  INSERT INTO enrollments (...);
  INSERT INTO outbox_events (event_type, payload, idempotency_key);   -- same txn!
COMMIT;
-- separate poller reads outbox -> publishes to Kafka -> marks sent
```
The event is committed atomically with the business state. You can't have an enrollment without the corresponding event eventually being published. This is one of the few places analytics-related work sits inside the source transaction — but it's just the *intent to publish*, not the analytics computation.

**2. Idempotent consumer** — solves "what if Kafka redelivers the same event?":
```sql
BEGIN;
  INSERT INTO processed_events (event_id) ON CONFLICT DO NOTHING;
  -- if 0 rows inserted, we already processed this -> bail
  UPDATE course_stats SET enrolled_count = enrolled_count + 1 WHERE course_id = ?;
COMMIT;
```
The transaction here is for atomicity of "mark processed AND update aggregate" together. Without that, a crash between the two leaves you double-counting on retry.

**3. Optimistic concurrency on counters** (when contention is high):
```sql
UPDATE course_stats
SET enrolled_count = enrolled_count + 1, version = version + 1
WHERE course_id = ? AND version = ?
```
If `version` changed, retry. Lighter than `FOR UPDATE` because there's no lock — readers and writers don't block each other. Useful when many consumers update the same aggregate row.

**TL;DR:**

| Question | Answer |
|---|---|
| Will analytics use transactions? | Yes. |
| The same transaction as enrollment? | No. That's the whole point of async analytics. |
| For the same reason (race control)? | No. For idempotency, atomic counter updates, exactly-once event processing. |
| Will some "analytics-adjacent" work sit inside the enrollment txn? | Yes — the transactional outbox pattern. But it writes intent-to-publish, not analytics state. |

---

### Q: If T1 (enrollment) commits but T2 (analytics counter update) fails, is T1 rolled back / withheld?

**A:** **No. T1 stays committed.** Once `COMMIT` returns success, the data is durable — the "D" in ACID. There is no mechanism to un-commit; you can only write a compensating transaction, and for analytics failures the business does NOT want that.

**Why withholding T1 would be wrong** — it re-couples the two services and brings back every problem we split them to avoid:

1. A bug in the analytics service blocks all enrollments (user-facing 500s for a reporting bug).
2. Downed Kafka prevents users from enrolling — your "Kafka for resilience" claim becomes "Kafka is a hard dependency."
3. Hot analytics tables cause lock contention back on the enrollment path.
4. Latency rises — every enrollment waits for aggregation.

This is the **distributed monolith** anti-pattern: looks distributed but fails like a monolith because failures cascade across components. The system is deliberately designed so enrollments succeed even if analytics is down for a week. Analytics catches up later.

**What actually happens when T2 fails:**

| Failure | What happens | Recovery |
|---|---|---|
| Kafka publish fails right after commit (network blip) | Without outbox: event is LOST -> dual-write problem | **Transactional outbox** — write event in same txn as T1; poller retries |
| Celery worker crashes mid-update | T2 auto-rollback; message ack not sent | Another worker picks up; idempotency table prevents double-count |
| Bug makes T2 fail repeatedly | Hits retry limit -> dead-letter queue; alert fires | Engineer fixes + replays DLQ; enrollments unaffected meanwhile |
| Analytics DB unavailable | Consumers can't commit -> queue backs up (backpressure) | Drain when DB returns; dashboard shows lag until caught up |
| Kafka redelivers same event | T2 runs again | Idempotency table catches duplicate via `INSERT ON CONFLICT DO NOTHING` |

Pattern is always: **forward progress only, no rollback of T1**. Eventually consistent, not transactionally consistent across components — a deliberate trade.

**The three safety nets that make "eventually consistent" actually safe (Week 3):**

1. **Transactional outbox** — closes the dual-write hole. Write the event in the same DB txn as T1; a separate poller publishes to Kafka with retries. You cannot have an enrollment without the corresponding event eventually reaching Kafka.

2. **Idempotent consumer** — closes the redelivery hole. `INSERT INTO processed_events (event_id) ON CONFLICT DO NOTHING` inside T2; skip if already processed. Kafka can redeliver a thousand times; the count stays correct.

3. **Reconciliation job** — closes the "drift forever" hole. A nightly job recomputes aggregates from the source of truth:
   ```sql
   UPDATE course_stats cs
   SET enrolled_count = (SELECT count(*) FROM enrollments
                         WHERE course_id = cs.course_id AND status = 'active');
   ```
   Source of truth (T1's tables) is always right; derived data is always recoverable.

**Mental model (CAP theorem in practice):**

- **Strong consistency** on source of truth (enrollments table) -> guarded by T1 with `FOR UPDATE`.
- **Eventual consistency** on derived data (analytics) -> guarded by T2 + idempotency + reconciliation.
- **Availability** of both — neither blocks on the other.

Saga pattern at the data layer: forward-only progress, with compensating actions that live in the analytics replay logic — NOT in undoing the user's enrollment.

**Anti-patterns to reject (someone will suggest all three eventually):**

| Suggestion | Why it's wrong |
|---|---|
| Use two-phase commit (2PC) across DB and Kafka | 2PC requires a coordinator; Kafka doesn't fully support it; slow; makes every component a SPOF. Industry moved away from it. |
| Reverse the enrollment if analytics fails | Punishes the user for an internal bug. Also racy — user may have done other things by then. |
| Block the enrollment response until T2 confirms | Destroys the latency benefit. You've rebuilt the fat transaction. |

---

### Q: According to PRD and Part A, do we have two transactions — one for enrollment and one for analytics?

**A:** **Yes, in the sense that matters:** the **durable enrollment** is committed in the **API request’s PostgreSQL transaction(s)** (source of truth). **Analytics updates** are applied in **separate transaction(s)** on the async path (after the event is consumed), not rolled back with the user’s enroll if analytics fails.

**Nuance — transactional outbox (Week 3):** You may put an **outbox row** (intent to publish) in the **same** DB transaction as the enrollment insert so you never lose the event. That is still not “run full analytics in T1” — the **aggregate / metric write** stays in **T2**. So: one txn for “user is enrolled + event recorded for delivery”; another txn(s) for “dashboards reflect it.”

**PRD alignment:** [PRD.md](PRD.md) **NFR-C05** and the Enrollment Workflow bullets describe enrollment as independent commit and analytics as async / eventual consistency.

---

### Q: Before going further — why do we need Temporal workers and Celery?

**A:**

**Why any workers at all?** FastAPI returns quickly; users should not wait on indexing, email, multi-step publish, or analytics. Workers run **outside** the request: retries, backoff, and crashes do not become user-facing 500s on the critical path.

**Temporal (workflow + worker)** — for **orchestrated, stateful, multi-step** processes where order, retries, and **compensations** matter:

- **Course publishing** (Part A): validate → process content → mark published; if step 3 fails, undo step 2 in reverse order. Temporal keeps **durable workflow state**, replays workflow code safely, and retries **activities** with policies you configure.
- You **could** fake this in Celery with chains and manual saga tables, but you re-implement persistence, dedupe, timeouts, and recovery. Temporal is built for that.

**Celery (task workers)** — for **discrete, idempotent jobs** that do not need a persisted multi-step graph:

- Send welcome email (stub: log to console).
- Bump analytics aggregates, warm cache, one-off maintenance.
- Simple “do this once per event” work with RabbitMQ as broker.

**Why not only Celery?** Celery is great at “run task X,” weak at “guarantee this exact 5-step saga with compensations across partial failures and process restarts” without a lot of custom code.

**Why not only Temporal?** Overkill for a one-shot email or a single counter update; more moving parts and operational surface for trivial work.

**Rule of thumb (from [CLAUDE.md](../CLAUDE.md)):**

| Need | Tool |
|------|------|
| Single DB transaction (enroll + lock) | Postgres + `AsyncSession`, no worker |
| One side-effect, retry independently | **Celery** |
| Multi-step with state + compensations | **Temporal** |
| Long-running / human approval | **Temporal** |

**“Temporal worker” vs “Celery worker”:** both are separate processes that pull work from a queue — but Temporal’s queue is **workflow and activity tasks** with a server that records history; Celery’s queue is **messages** for individual tasks. Different products, complementary in this stack (Kafka can still fan out events; Celery can consume them or run scheduled jobs).

---

### Q: How do Kafka, Celery, and Temporal fit together according to our PRD? What is the Saga pattern?

**A — how the three fit the PRD (Part A):**

Our [PRD](PRD.md) asks for: (1) **publishing** without corrupting state on partial failure, (2) **enrollment-driven** analytics and notifications **async**, (3) **event-driven** behavior with **no double-processing**, **traceability**, and **spike handling**.

Think in **three lanes**:

| Lane | Tool | PRD it serves |
|------|------|----------------|
| **Orchestrated workflows** | **Temporal** | **Content publishing** (FR §2): multi-step pipeline (validate → process → mark published / ready), compensations if something fails, durable state across crashes. The **Temporal worker** runs workflow + activity code the server schedules. |
| **Event fan-out** | **Kafka** | **Distributed & event-driven** (FR §4): after something commits in Postgres (`user.enrolled`, `course.published`, `lesson.completed`), **publish facts to a log** so *many* subscribers can react without the API knowing them all. Handles **backpressure** and **spikes** (buffer), supports **Schema Registry** for contract evolution. |
| **Task execution** | **Celery** | **Side-effect jobs** (FR §3 notifications, FR §4 analytics updates): “send email,” “increment aggregate,” “warm cache.” RabbitMQ is the **broker** Celery uses. Often a **consumer** reads Kafka → **enqueues** Celery tasks (Kafka is not a replacement for a task queue here). |

**One plausible end-to-end flow (aligned with PRD, not all built yet):**

1. **Publish course:** FastAPI `POST .../publish` → **Temporal** starts `CoursePublishingWorkflow` (202). Worker runs activities (DB reads/writes). On success, emit **`course.published`** to **Kafka** (or transactional outbox → publisher).
2. **Student enrolls:** API commits enrollment → **transactional outbox** row or **`user.enrolled`** to Kafka.
3. **Downstream:** Kafka consumers (or a bridge) trigger **Celery** tasks: welcome email, analytics rollup, cache invalidation — **independently**, **retriable**, **idempotent**.

So: **Temporal** owns **long-running orchestration + compensation** for publishing; **Kafka** owns **durable event stream + fan-out**; **Celery** owns **discrete async work**. They compose; they do not replace each other.

```mermaid
flowchart LR
  subgraph api [FastAPI]
    R[Routes]
  end
  subgraph temporal [Temporal]
    TW[Temporal worker]
    WF[Publish workflow]
  end
  subgraph kafka [Kafka]
    T[Topics]
  end
  subgraph celery [Celery]
    CW[Celery workers]
  end
  R -->|"start workflow"| TW
  TW --> WF
  WF -->|"emit events"| T
  R -->|"outbox or emit"| T
  T -->|"consume"| CW
```

---

**A — Saga pattern (what it is, and how we use it):**

A **Saga** is a pattern for **a business operation that spans multiple steps** (often multiple services or multiple DB writes) **without** a single distributed two-phase commit (2PC). Instead of one giant atomic transaction, you use a **sequence of local transactions**, each with a **compensating action** if a later step fails.

**Two styles:**

| Style | Who coordinates | Notes |
|-------|-----------------|-------|
| **Choreography** | Each service listens and decides what to do next | Loose coupling; global flow is harder to see; ordering can get messy. |
| **Orchestration** | One **orchestrator** drives steps in order | Clear flow, explicit failure handling; here the orchestrator is a **Temporal workflow**. |

**Compensating transaction:** not always a literal `DELETE` — whatever **semantically undoes** the forward step (e.g. revert course to `draft`, delete processed artifacts). Compensations run **in reverse order** of completed steps.

**Example for our publish saga (orchestrated in Temporal):**

1. **Step A (read-only validate):** course exists, draft, owner, has content. *No compensation.*
2. **Step B (process):** write processed markers / placeholder pipeline. *Compensation:* delete that processed data.
3. **Step C (publish):** set `status = published`. *Compensation:* revert to `draft`.

If **C** fails after **B** succeeded → run **B’s compensation**, then surface failure. If **B** fails → nothing to compensate from **A**. Temporal **retries activities**; activities must be **idempotent** (deterministic keys → same effect) because retries happen.

**Saga vs “just use Kafka”:** Kafka delivers **events**; it does not by itself remember “we were on step 2 of 3 and must compensate.” You still need **orchestration logic** somewhere — handwritten state machines + DB, or **Temporal** with persisted workflow history and replay.

**Saga vs Celery chain:** A Celery chain can order tasks, but **durable saga state**, **replay-safe workflow code**, and **first-class compensation** after exhausted retries are weaker without building a lot yourself; Temporal is the deliberate choice for **publishing** in this project.

**PRD pointers:** publishing + partial failure → [PRD.md](PRD.md) §2; events + analytics + notifications → §3–4 and **NFR-C05**; Temporal playbook → [CLAUDE.md](../CLAUDE.md) Saga / Temporal section.

---

### Q: Which comes on top or first — Kafka, Celery, or Temporal?

**A:** There is **no single global stack** with one always “on top.” **Order is per user action** (per use-case). Almost always:

1. **First:** **FastAPI + PostgreSQL** — auth, validation, commit (the synchronous request). The user’s durable state is decided here for enroll (and for “start publish,” only “workflow started” + 202, not “course is published” yet).

2. **Then (async):** depends on the flow:

| Use-case | First async | Then typical chain |
|----------|-------------|---------------------|
| **Publish course** | **Temporal** (`start_workflow` from API) | Temporal **activities** (DB). On success → **Kafka** `course.published` → consumers may call **Celery** (email, index, metrics). |
| **Enroll** | **Kafka** `user.enrolled` (after commit; often via outbox) | Consumer → **Celery** (welcome email, analytics). **Temporal not required** for vanilla enroll. |

**Memory aid:** **API+DB first** always for the HTTP request. Among async tools: **Temporal leads** when you need a **multi-step saga with compensations** (publish). **Kafka leads** when you need to **broadcast a fact** to many subscribers. **Celery** often **follows Kafka** (or runs on a schedule) to **execute** a concrete task.

**“Top” in architecture diagrams:** the **client** and **API** are “top” (entry). Temporal / Kafka / Celery are **peers below** the API, wired differently per flow — not a vertical ranking of superiority.

---

### Q: Are we good to go ahead with Part B?

**A:** **Not as the next committed delivery track**, if we follow the official Part A → Part B plan. **Part A = Weeks 1–3** (foundation, enrollment + publishing workflow, events + observability). **Part B = Weeks 4–5** (GenAI) and explicitly builds on Part A (e.g. chunking pipeline, events like `lesson.created`).

**Current state (typical repo trajectory):** Week 1 ✅; Week 2 Chunk A (enrollment) ✅; Week 2 Chunk B (Temporal publishing) ✅; Week 3 (Kafka, Celery, analytics, observability) ⬜. Starting Part B **before** those leaves gaps: weaker event bus for lesson lifecycle, observability for RAG latency work.

**When you *are* good for Part B:** after Part A scope is done **or** your mentor agrees to a **reordered plan** (document the tradeoff: you accept missing integration until Week 3 catches up).

**Parallel spikes:** OK for learning (local notebooks, small embedding demos); not a substitute for finishing Part A for the graded / integrated system.

---

### Q: Are we good to go ahead with Week 2 Chunk B (Temporal publishing)?

**A:** **Yes.** Chunk A (enrollment) is complete; the planned next step in Part A Week 2 is **Chunk B**: Temporal SDK, worker, publishing workflow with compensations, `POST /courses/{id}/publish` returning **202** + workflow id, tests via `temporalio.testing.WorkflowEnvironment`. Prerequisites: course/module/lesson models, draft/published semantics, [CLAUDE.md](../CLAUDE.md) Saga section, `docker-compose --profile week2` for Temporal + UI.

---

### Session: 2026-05-13 — Temporal first-time: sessions, factories, queues vs RabbitMQ

### Q: Why does `app/temporal/activities/course_publish.py` use its own session scope instead of FastAPI `get_db`?

**A:** **`get_db` is request-scoped** — FastAPI opens a session for one HTTP handler and closes it after the response. **Temporal activities never go through FastAPI**; they run on the **worker** when Temporal invokes them. So activities need an explicit **open session → work → commit/rollback** path. `_session_scope()` mirrors the same **try / commit / except rollback** pattern as `get_db`, but callable from activity code without `Depends()`.

### Q: What is a session factory here?

**A:** **`async_sessionmaker`** (e.g. `AsyncSessionLocal`) is the factory: each call `AsyncSessionLocal()` creates a **new** `AsyncSession` using the shared engine pool. In `course_publish.py`, `configure_activity_session_factory` lets **tests** point activities at the **test DB** sessionmaker; in production the worker leaves it unset and uses `app.database.AsyncSessionLocal`.

### Q: What is an async context manager?

**A:** An object (or `@asynccontextmanager` function) usable with **`async with`**: setup runs on enter, cleanup on exit (including on exceptions). `_session_scope()` yields a session then commits or rolls back — same idea as `get_db`’s `yield` + commit/rollback.

### Q: What are Temporal’s main pieces and how does a run work?

**A:** **Server** — durable **workflow history** (not your app Postgres). **Client** (API) — `start_workflow` / describe / query. **Worker** — long-lived process polling a **task queue**, executing **workflow** code (orchestration, deterministic) and **activity** code (DB/HTTP side effects, retried). **Task queue** — a name both starter and worker agree on (e.g. `course-publishing`). Server schedules tasks; workers pull; you scale by **more workers** on the same queue.

### Q: RabbitMQ has queues too — why both Temporal and RabbitMQ?

**A:** **RabbitMQ** (with Celery) is ideal for **many independent tasks** and simple fire-and-forget work. **Temporal** is for **multi-step, stateful orchestration** with built-in history, replay, per-activity retries, and saga-style ordering. This project uses Temporal for **course publish** and plans RabbitMQ/Celery for other async work — they complement; neither fully replaces the other.

### Q: Do API, worker, and Temporal run on the same server?

**A:** **Locally**, often one machine with **separate processes** (uvicorn, worker, Temporal, Postgres). **In production**, they are usually **different** deployable units that only need network access to each other. App Postgres and Temporal’s own storage are **different** concerns.

### Q: Do we need a separate `temporal_worker.py` per workflow or per queue?

**A:** **No.** One worker process typically registers **multiple** workflows and activities on **one or more** task queues. You add another worker binary or queue only for **isolation or scaling policies**, not because Temporal requires one file per workflow.

---

### Q: Interview-style — RabbitMQ vs Kafka vs Celery vs Temporal; are they the same?

**A:** **No** — different layers and purposes:

| Piece | Role |
|-------|------|
| **RabbitMQ** | **Message broker** — queues/routing; typical **Celery broker** for task messages. |
| **Kafka** | **Distributed log / event stream** (topics, partitions) — durable **facts** many consumers can read; **replay** by offset; not “one consumer deletes for everyone” like a simple work queue. |
| **Celery** | **Task framework** — workers execute **discrete tasks** pulled from a broker (RabbitMQ, Redis, …). |
| **Temporal** | **Workflow platform** — **server** stores **workflow history**; **workers** run **workflows** (orchestration) and **activities** (side effects, retried). Task **queues** route work; the product is **stateful orchestration**, not just a queue. |

**Composition:** Celery often uses **RabbitMQ**. **Kafka** can feed work into Celery (consumer → enqueue task). **Temporal** can coexist with both (e.g. publish saga in Temporal; analytics/email via Kafka → Celery). They **complement**; they do not replace each other for every use case.

### Q: Is “two Celery workers” like extra Gunicorn workers?

**A:** **No.** **Gunicorn/Uvicorn workers** handle **HTTP** for the API. **Celery workers** pull **background tasks** from the **broker**. More Celery processes = more **async job** capacity, not more web request workers. One host can run both, as separate process pools.

---

### Q: What is a message broker? Fan-out? Kafka vs RabbitMQ with real-life examples? Is Redis a queue?

**A:**

**Message broker** — middleware between **producers** and **consumers**: accepts messages, buffers/routes them, delivers so senders don’t depend on receivers being up.

**Fan-out** — **one** message/event is **distributed to many independent consumers** (each does its own work). Example: “flight cancelled” → push notification service, email service, analytics, and partner API all react.

**Kafka** — append-only **event log** (**topics**). Producers **append** records; **consumer groups** each track an **offset** (read position). Many groups on the same topic ≈ **fan-out** of the same stream. Good for **facts** (`user.enrolled`) and **replay**. Consumers **react** (update DB, enqueue Celery, metrics).

**RabbitMQ** — **brokered queues** (often **one consumer** takes a message, **acks**, message leaves queue). Good for **jobs** (“send email”, “generate PDF”). **Celery** commonly uses RabbitMQ (or Redis) as the **broker**; Celery **workers** **act on** those task messages.

**Real-life analogy:** RabbitMQ ≈ **order ticket** on a kitchen rail (**next cook** grabs **one** job). Kafka ≈ **bank ledger line** everyone can **read**; teams keep their own **bookmark**; new analytics can **re-read** history.

**Redis** — in-memory **data store**; not “only a queue.” It **can** implement queues (**Lists**, **Streams**) or be a **Celery broker**, but it is not the same product category as RabbitMQ/Kafka alone.

---

### Q: Does Celery put messages into a RabbitMQ queue?

**A:** **Yes**, when RabbitMQ is configured as the **Celery broker**. `task.delay()` / `apply_async()` publishes a **serialized task message** to RabbitMQ (via Celery’s exchange/routing); **workers** consume from the queue, execute the task, and **ack**. With a **Redis** broker, the payload goes to Redis instead—same pattern, different transport.

---

### Q: Is Celery the worker that attaches to RabbitMQ? Does Kafka have no workers for events?

**A:**

**Celery** is a **framework**, not one process. Your **API** (or any code) uses Celery as a **client** to **publish** task messages to the **broker** (e.g. RabbitMQ). **Celery worker** processes are **separate** long-running processes (`celery -A app worker`) that **connect to that broker**, **consume** queue messages, and run `@task` functions. So: **RabbitMQ** stores the queue; **Celery workers** attach and pull work.

**Kafka** does not include Celery. Events live in **topics**. **Consumer applications** (your services using a Kafka client, or stream processors) **subscribe / poll**, process each record, and **commit offsets**. Those consumers are **worker-like** but are **your** processes—not “Celery” unless you explicitly wire Kafka consumption into Celery tasks.

---

### Q: Who adds events to Kafka? Does Kafka have its own system?

**A:** **Producers** add events — application code (or Kafka Connect, stream jobs, test CLIs) using a **Kafka producer client** that **appends records to topics**. Kafka does not infer business rules by itself; it **stores, replicates, and serves** the log your producers write.

**Kafka is its own distributed system:** broker processes, topic partitions, replication, retention, consumer groups and offsets, and cluster metadata (ZooKeeper or **KRaft**). You operate or buy that infrastructure; your services are **clients** that produce and consume.

---

## Session 4 — 2026-05-14

### Q: How should the frontend manage roles — server session or something else?

**A:** Mirror the backend, which is **stateless JWT — there is no server session**. So the frontend is also sessionless:

- **Login** posts the OAuth2 password form to `/auth/login` and gets a JWT back. Store it in `localStorage` (`smartcourse_token`). An axios request interceptor attaches `Authorization: Bearer <token>` on every call.
- **Role is not decoded from the token on the client.** Right after login (and on every app load with a stored token), `AuthContext` calls `/users/me` and keeps the returned `User` — including `role` — in React state. Role-dependent UI (nav links, route guards) is driven by that record.
- **The client is never the authority.** Route guards (`ProtectedRoute`) are a UX convenience; the backend re-checks role and ownership on every request regardless. A tampered token fails server-side, and an axios response interceptor clears it on any `401`, bouncing the user to `/login`.

Why not a server session? It would mean adding session storage (Redis), a session cookie, CSRF protection, and a logout endpoint — state the system deliberately avoided. JWT keeps the API horizontally scalable (any worker can validate a request with no shared session store). Why not trust a client-decoded JWT for role? Because the client can't verify the signature meaningfully and the token can go stale (e.g. a deactivated account) — `/users/me` is the single source of truth, and it's one cheap call.

### Q: Why did adding a frontend require new backend endpoints?

**A:** Three read endpoints were added — `GET /courses/mine`, `GET /courses/{id}/modules/{mid}/lessons`, `GET /enrollments/{eid}/progress`. None are new *features*: they expose data the system already owns but had no read path for. The original API was write-biased (you could `POST` a lesson but not `GET` the list), which is fine for curl-driven testing but leaves a UI unable to render. The alternative — having the frontend cache created IDs in `localStorage` — would have put source-of-truth state in the browser, which violates "PostgreSQL is the source of truth." Exposing existing data through the proper Router → Service → Repository layering was the smaller, more correct change.

### Q: Final storage architecture (resolved) — where do chunks, embeddings, and analytics actually live?

**A:** This consolidates and supersedes the earlier, drifting answers above. The driving constraint: **Part A explicitly mandates a NoSQL DB** (PRD.md:211), so MongoDB needs a job it *genuinely* fits — not a forced one.

**Embeddings → PostgreSQL + pgvector.** Embeddings exist to be similarity-searched (ANN). pgvector is purpose-built — HNSW indexes, cosine distance, free, inside the Postgres we already run. Mongo's `$vectorSearch` is Atlas-first and weaker self-hosted. The embedding is FK'd to a chunk FK'd to a lesson, so one JOIN yields "the vector + the lesson/module/course context" — the whole RAG retrieval query.

**Chunks → PostgreSQL, same row as the embedding.** A chunk and its embedding are one row: `{ lesson_id, course_id, chunk_index, text, embedding }`. "Chunks in Mongo" only made sense while embeddings were *also* going to Mongo; once embeddings move to pgvector, splitting chunk-text-in-Mongo from embedding-in-Postgres would force a cross-database join on every retrieval. Chunks are not "unstructured" — fixed fields, FK to lesson, queried as "all chunks for lesson X in order." The earlier "chunks are unstructured text" justification (QA.md, *Where does content get stored…*) was the weak link.

**Analytics — the 9 dashboard metrics → PostgreSQL SQL.** Total students, completion rate, popular courses, etc. are counts/averages/group-bys/JOINs over tables we already have. A materialized view handles that well past 50k users. No document store needed to *compute* them.

**MongoDB → the raw interaction/event log.** Not the 9 metrics — the granular behavioral stream *underneath* them: `lesson.viewed`, `video.paused@03:12`, `search.performed(...)`, `quiz.answered`. PART_A names this exact problem in its own words — *"rich but underutilized data"* (PART_A.md:13), *"not leveraged for recommendations"* (PRD.md:17). It is a genuine document-store fit:
- high write volume, append-only — every interaction, never updated
- schema varies per event type — a `payload` document beats 20 nullable SQL columns
- not the source of truth (Postgres is) — losing one event doesn't corrupt user state; it is the async category
- no transactional JOINs with the core — it is a sink: Kafka/Celery write into it, batch jobs roll it up

| Store | Holds | Why |
|---|---|---|
| PostgreSQL | users, courses, modules, lessons, enrollments, progress, certificates **+ chunks + embeddings (pgvector)** | source of truth; relational; ACID; ANN search co-located with the data it describes |
| MongoDB | one `events` collection — raw interaction/event log | high-volume, append-only, per-event-type flexible schema; the "underutilized data" PART_A calls out |
| Postgres aggregates | the 9 dashboard metrics | SQL rollups over core tables + the event log |

**Consequences:** overrides the earlier "MongoDB = lesson_chunks / no chunks in Postgres ever" decision. pgvector requires swapping the Docker image to `pgvector/pgvector:pg15` — a one-line Week 4 change. The `text` lesson question (lessons needing a `content_text` column instead of a fake URL) is still open and orthogonal to this.

### Q: How long does a Temporal workflow normally take, and where do we watch it?

**A:** **Temporal UI → http://localhost:8080** (the `temporal-ui` container). Find a run by Workflow ID `publish-<course_id>`; the Event History shows each `ActivityTaskScheduled/Started/Completed` and the final status.

For our `CoursePublishingWorkflow` the normal happy path is **sub-second — roughly 100–500ms locally.** It is 3 sequential activities, all trivial DB work (a SELECT + COUNT, then SELECT + UPDATE, then SELECT + UPDATE). The visible time is mostly Temporal's orchestration overhead: each `execute_activity` is a round trip — workflow → server → task queue → worker long-poll → execute → report back → workflow resumes — ~10–50ms per hop locally.

The per-activity `start_to_close_timeout` (120s in our code) is a **ceiling, not the expected duration** — a healthy run never approaches it.

What stretches a run (and is usually not "slowness"):
- **Worker not running** — the workflow starts, activity tasks queue on `course-publishing`, nothing consumes them. With no `schedule_to_start` timeout set, it stays **Running indefinitely**. A stuck-on-Running workflow almost always means the worker process is down.
- **Transient (retryable) failure** — our real validation errors raise `ApplicationError(non_retryable=True)` and fail instantly. But a generic exception (e.g. DB briefly unreachable) hits Temporal's default retry policy: exponential backoff 1s -> 2s -> 4s -> 8s..., unlimited attempts — which can extend a run to minutes.

Future caveat: once `process_lessons_activity` becomes the real Week 4 chunking + embedding pipeline, *that* activity legitimately becomes the long pole (seconds to minutes), and it should get its own tuned timeout + retry policy.

### Q: Should the Temporal worker have its own Dockerfile, or share one with the API?

**A:** **One Dockerfile, one image, two `command:`s.** The worker is not a separate application — it is the same `app` package, the same `requirements.txt`, the same `.env`, the same models/config/db code. The only difference is the entrypoint: the API runs `uvicorn app.main:app`, the worker runs `python -m app.workers.temporal_worker`. docker-compose builds the image once and runs it in three roles — `migrate`, `api`, `worker` — by overriding `command:`.

Why one image, not two:
- **Version lock.** API and worker provably run identical code. Two Dockerfiles invite drift — the worker built from a stale commit while the API moved on. For Temporal that is not cosmetic: workflow code that differs between the run that started and the worker that replays it causes **non-determinism / replay failures**, the failure class Temporal punishes hardest.
- **Build once.** One build context; each service just overrides `command:`. Simpler CI, smaller footprint.
- **Scales trivially.** `docker compose up --scale worker=3` off the same image — workers are stateless.

The single build anchor is the `migrate` service: it is the common `depends_on` of both `api` and `worker`, so building it once produces the shared `smart-course-app` image and avoids a parallel-build race on the image tag (`api`/`worker` carry only `image:`, no `build:`).

When you *would* split — and it is not now: once `process_lessons_activity` becomes the real Week 4 chunking + embedding pipeline, it pulls in heavy deps (torch / sentence-transformers / pypdf / faster-whisper, hundreds of MB) the API never needs. Even then the answer is not two Dockerfiles — it is **one multi-stage Dockerfile with `api` and `worker` build targets** sharing a base. Pre-building that today is YAGNI.

Operational note: `temporalio/auto-setup`'s `tctl cluster health` healthcheck reports the *frontend* ready, but the *matching* service can still be a few seconds behind — so a freshly-started worker logs `"Not enough hosts to serve the request"` for ~10–15s. The Temporal SDK auto-retries and the container has `restart: unless-stopped`; it self-heals without intervention. That retry-and-recover behaviour is the correct design, not a bug to paper over.

### Q: We add an outbox to avoid losing events to Kafka — but couldn't the outbox row also fail to land? Aren't we just moving the same problem?

**A:** No, and the difference is one word: **transaction**. The outbox row is an `INSERT` into the *same Postgres* as the business write, *inside the same transaction*:

```sql
BEGIN;
  INSERT INTO enrollments(...)  → row 999;
  INSERT INTO outbox(...)       → event row keyed enrollment-999;
COMMIT;
```

Those two `INSERT`s are one atomic write. Postgres's ACID guarantee means they *both* land on disk or *neither* does — Postgres's WAL backs this even through a power cut. There is no failure mode where the enrollment commits but the outbox row vanishes; they share a single commit.

The Kafka dual-write problem looks different:

```
COMMIT enrollment in Postgres ✓
... gap ...
send event to Kafka       ← different system, different network, different ack
```

Two writes to two systems, two ack points, an unavoidable gap. *That* gap is where events get lost (process crash, network drop, broker down). No ordering of the two writes is safe.

The outbox collapses "DB write + emit event" into "DB write only" at commit time — the event becomes part of the same atomic write the user is already doing.

**"But the relay still talks to Kafka — same problem there?"** No: the outbox row is already durably committed in Postgres before the relay tries anything. If the relay crashes mid-send, the row sits there with `sent_at = NULL` and is retried on restart. If Kafka is down for an hour, outbox rows queue up and drain when it returns. **The event cannot be lost** — the worst case is delay, or a *duplicate* on Kafka (relay retried after a dropped ack), which is exactly what consumer-side idempotency keys + dedupe handle.

The layering:

| Concern | Solved by |
|---|---|
| Event might never be emitted (lost) | **Outbox** — atomic with the business write |
| Event might be emitted twice (duplicate) | **Idempotency key + consumer dedupe** |
| → | **Effectively-once delivery** |

### Q: Walk me through the idempotency-key + dedupe pattern with a real example. What is TTL? What does "dedupes" mean?

**A:** **Dedupe** = "deduplicate" = "skip a message we have already processed." Standard ops shorthand.

Concrete run-through. Alice clicks Enroll on the Python Bootcamp course; her enrollment row gets `id=999`.

```
1. POST /courses/123/enroll
2. In ONE Postgres transaction:
     INSERT INTO enrollments(...)   → id=999
     INSERT INTO outbox(...)        → { event_type: "user.enrolled",
                                        event_key:  "enrollment-999",
                                        payload:    {enrollment_id:999, ...} }
   COMMIT
3. Return 201 to Alice
```

A separate **relay** polls the outbox, finds the row, publishes to Kafka topic `events.user.enrolled` with idempotency key `enrollment-999`. Here's the failure that makes the key necessary:

```
relay → Kafka:  "message {key: 'enrollment-999', ...}"
Kafka:          accepted, persisted ✓
Kafka → relay:  "ack"  ← network drops the ack
relay:          "no ack — retry"
relay → Kafka:  same message again
Kafka:          accepted, persisted ✓ (Kafka does not deduplicate on its own)
```

Kafka now has **two physical copies** of one business event. Three consumer groups (welcome-email, analytics, recommendations) each read both copies. Without dedupe: 2 welcome emails, 2 analytics rows, numbers diverge from Postgres.

The **idempotency key** ties the two physical Kafka messages back to one real-world event. Both copies carry `enrollment-999` because we computed the key from the row id, not from anything Kafka-specific.

The consumer's loop, before any side effect:

```python
def on_message(msg):
    key = msg.headers["idempotency_key"]   # "enrollment-999"
    if already_processed(key):
        return                              # duplicate — skip
    do_the_work(msg)                        # send email / write Mongo / etc.
    mark_processed(key)
```

Delivery #1: `already_processed("enrollment-999")` → False → email sent → key recorded. Delivery #2: → True → skip. Alice gets one email.

**Where the "already processed" record lives — two options:**

**Postgres `processed_events` table** (durable, no TTL):
```sql
INSERT INTO processed_events (event_key, processed_at)
VALUES ('enrollment-999', NOW())
ON CONFLICT (event_key) DO NOTHING;
-- Rows inserted = 1  → first time, do the work
-- Rows inserted = 0  → duplicate, skip
```

**Redis `SET ... NX EX`** (fast, auto-expires):
```
SET processed:enrollment-999 1 EX 86400 NX
```
- `EX 86400` → **TTL (Time To Live) of 86,400 seconds = 24 hours.** Redis auto-deletes the key after that. TTL is a generic Redis feature — entries can be given an expiry timer.
- `NX` → only set if it does **N**ot e**X**ist. This makes it dedupe-safe.

First delivery: key doesn't exist → SET returns "OK" → do the work. Second delivery (within 24h): key exists → SET returns nil → skip. Past 24h: key auto-expired; if a redelivery somehow showed up *26 hours later* it'd slip through (extremely rare — Kafka redelivers within seconds, not hours).

| | Postgres `processed_events` | Redis `SET NX EX` |
|---|---|---|
| Speed | DB roundtrip per event | Sub-millisecond, in-memory |
| Durability | Survives anything | Lost if Redis crashes without persistence |
| Memory | Grows forever (or archive) | TTL auto-cleans |
| Late-redelivery gap | None | Beyond TTL, slips through (rare) |

Combined with the outbox: outbox → no lost events; idempotency key + dedupe → no double-applies. That's **effectively-once**.

### Q: Why is the suggested order better than the doc's checklist? Show with examples.

**A:** The doc's order is 14 items in some list; it does not tell you what to build first. The suggested order is about **proving the pattern end-to-end on one event before scaling out**. Concrete contrast:

**Doc order — Mon to Fri, hypothetical:**

| Day | Action | What breaks |
|---|---|---|
| Mon | Spin up Kafka, write `user.enrolled` producer. Events appear in `kafka-ui`. | Looks fine. |
| Tue | Add `course.published` + `lesson.completed` producers. | 3 producers, **0 consumers** — no way to tell if payloads are even useful. |
| Wed | Schema registry + idempotency keys on producers. | Still no consumers. Keys exist but have nothing to dedupe against — untested. |
| Thu | Finally: Celery worker + Kafka→Celery bridge + welcome-email task. Discover the `user.enrolled` payload **doesn't include `student_email`** — task can't send anything. Edit producer, redeploy, redo schema. Then discover the consumer is receiving duplicates — **dedupe was never implemented**, only keys emitted. Half a day debugging cross-system. | Three things broken at once. |
| Fri | Half a day left. Analytics not started. Observability nowhere. | 60% done across everything; nothing end-to-end. |

Each layer was built without seeing the next.

**Suggested order — same week:**

| Day | Action | What gets proved |
|---|---|---|
| Mon AM | Decide `user.enrolled` payload by walking backwards from the welcome-email task: it needs `student_email`, `course_title`. So those go in the payload (or thin payload + consumer fetches from DB). **Consumer-driven design.** | Payload right the first time. |
| Mon PM | Outbox table + Alembic migration; `enrollment_service` writes to outbox in same TX; verify outbox row appears on enroll. | Producer half works. |
| Tue AM | Kafka→Celery bridge consumer, `processed_events` dedupe table, welcome-email Celery task (logs to console). **One event flows all the way through.** | Pattern proven end-to-end in 1.5 days. |
| Tue PM | Stress-test failure modes: kill Kafka mid-relay (verify retry), inject duplicate (verify dedupe skip), crash consumer mid-process (verify offset behavior). | Pattern is *trusted*. |
| Wed | Copy for `lesson.completed` (~2h) and `course.published` (~2h, via Temporal activity — no outbox needed there). | Both new events working same day; scaffolding already exists. |
| Thu | Analytics endpoints — reading actual event data, not placeholders. | No rework. |
| Fri | Prometheus `/metrics` + structured logs (cheap). OpenTelemetry + Jaeger if time. | Observability instruments code that *exists*. |

**The principle:** debugging one broken thing is hard; debugging three half-broken interlocking things in parallel is hell. Get one full slice working before stamping out the other two.

### Q: What does "TX" mean in the outbox discussion?

**A:** TX = **database transaction** — the ACID-atomic kind. A `BEGIN ... COMMIT` block in Postgres. Everything between those two points is one unit: all statements land together (`COMMIT`) or none of them do (`ROLLBACK`, or a crash).

In our FastAPI setup the TX is implicit — managed by the `get_db()` dependency in `app/database.py`. One HTTP request = one session = one transaction. The handler runs all its work against the same `db` session, and the dependency commits (or rolls back on exception) right before the response is returned.

```
request → BEGIN → handler stages writes (INSERTs, UPDATEs) → COMMIT → response
```

Until `COMMIT` runs, the staged writes are invisible to any other transaction in the system. After it runs, they are durable (Postgres WAL backs this through power cuts).

When we say "both INSERTs are in the same TX," we mean: the enrollment row and the outbox row are both staged against the same session, and Postgres applies them with one commit. That's what gives us the "both-or-neither" guarantee that the outbox pattern depends on.

### Q: Is the outbox relay a scheduler (like cron)?

**A:** No — it's a **poller**, not a scheduler. Important distinction.

A scheduler fires at fixed times (every minute, every day at 3am) without knowing whether there is work to do. The relay is a **long-running process in a tight loop**:

```python
while True:
    rows = await fetch_unsent(limit=100)
    if not rows:
        await asyncio.sleep(0.5)
        continue
    for row in rows:
        await kafka.send(...)
        await mark_sent(row.id)
```

| | Scheduler (cron) | Our relay |
|---|---|---|
| Fires | At fixed times | Continuously, as fast as the loop |
| Knows about pending work | No | Yes — `WHERE sent_at IS NULL` |
| Latency from event to Kafka | Up to the interval | ~10–500 ms |
| Process model | Short-lived per tick | Long-running |

Closest Node analogy: a **BullMQ worker** — a process whose entire job is to drain a queue. Our "queue" happens to be a Postgres table instead of Redis, but the shape is the same. In our compose stack it will look like the Temporal worker: own service, same `smart-course-app` image, long-running.

At industrial scale you'd skip polling entirely and use Postgres logical replication via Debezium (Postgres *pushes* changes to the relay) — same idea, lower latency, more moving parts. Overkill for SmartCourse.

### Q: Doesn't RabbitMQ serve the same purpose as BullMQ / the outbox relay? What are the other options?

**A:** They're at *different points* in the pipeline. The words "queue" and "worker" get reused, but the roles are distinct.

| Tool | Role in SmartCourse | What it really is |
|---|---|---|
| Postgres `outbox` table | First durable hop — events land atomically with the business write | A regular table used as a queue |
| Relay process | Bridge — drains outbox into Kafka | A long-running Python loop. Not a broker. |
| Kafka | Fan-out distribution — many consumers read the same event log | Persistent, replayable log |
| RabbitMQ | Celery task broker — delivers specific work units to specific Celery workers | Traditional message broker |
| BullMQ (Node) | Mental model for Celery — same shape, Redis-backed task queue | A library, not a broker |

The big split: **Kafka = "dumb broker, smart consumer"** (log stays; multiple consumer groups read independently; replayable). **RabbitMQ = "smart broker, dumb consumer"** (once acked, gone; one consumer per task). We use **both** in the system, for different concerns:

```
POST /enroll  →  [outbox] → [relay] → [Kafka topic events.user.enrolled]
                                          │
                                          ├─► welcome-email consumer → RabbitMQ → Celery worker
                                          ├─► analytics consumer
                                          └─► recommendations consumer
```

The Celery+RabbitMQ pair lives *inside* each consumer's downstream path — it's the "execute the side effect" half. It doesn't replace Kafka, the relay, or the outbox.

"Can I skip the relay and publish to Kafka/RabbitMQ directly from the API?" → No. That's the dual-write problem. The broker on the other side doesn't matter; the relay's purpose is to make event emission atomic with a Postgres write.

**Other options for the relay's role**, increasing in latency-improvement and operational cost:

1. **Polling relay (what we have).** Simple, robust, sub-second latency. Right for SmartCourse-scale.
2. **Postgres `LISTEN/NOTIFY`.** The outbox INSERT fires `NOTIFY`; the relay is `LISTEN`-ing. Push-driven, sub-100 ms. Downside: `NOTIFY` isn't durable — if no one's listening that instant, the notification is lost. Pragmatic shape is LISTEN + poll as fallback.
3. **Debezium + Postgres logical replication (CDC).** Production-grade. Postgres streams row changes to a replication slot; Debezium turns the stream into Kafka messages. Zero polling, zero application code in the relay role. Downside: Kafka Connect cluster + Debezium plugin = more moving parts.
4. **Embed the event inside a workflow engine.** This is what `course.published` already does — emitted from inside a Temporal activity, whose history is the outbox-equivalent. Doesn't generalize to non-workflow flows.

Rule of thumb: **polling < LISTEN/NOTIFY < Debezium**. Polling is correct until you're past a few thousand events/second.

### Q: What's the difference between a cron job and the relay — technically and by usage?

**A:**

| | cron-style scheduler | Our relay (poller) |
|---|---|---|
| Process model | Short-lived. Fires, runs, exits. | Long-running. One process, infinite loop. |
| Triggered by | Wall-clock (every minute, at 3am, etc.) | An internal loop that wakes itself |
| Knows if there's work | No — runs regardless of inbox state | Yes — reads `WHERE sent_at IS NULL`; sleeps if empty |
| Time-to-action | Up to the interval (often minutes) | One loop tick (~500 ms in our config) |
| Failure recovery | Down cron = missed ticks | Restart policy keeps it alive; missed work waits in the outbox |
| Mental model | Calendar with reminders | A worker that paces itself by demand |

Same event, both approaches:

```
Cron every 1 minute:                       Relay (sleep 500 ms when idle):
  10:00:00.000  user enrolls                 10:00:00.000  user enrolls
  10:00:00.050  outbox row written           10:00:00.050  outbox row written
  10:01:00.000  cron fires                   10:00:00.250  relay's next tick
  10:01:00.180  message reaches Kafka        10:00:00.519  message reaches Kafka
  10:01:00.350  email sent                   10:00:00.700  email sent
  → ~60 second delay                         → sub-second
```

**Usage rule of thumb:**
- *Cron* fits periodic, work-doesn't-arrive-between-ticks jobs: nightly cleanup, daily reports, weekly archives, hourly health checks.
- *Relay-style poller* fits "work arrives at random times and latency matters": draining queues, syncing state, anything that touches a user's perception of timeliness.

In our project: the outbox relay is a poller; a future "archive sent outbox rows older than 7 days" job would be a cron.

### Q: Is it the right approach to run a dedicated long-running process just for the relay?

**A:** For SmartCourse-scale, yes. The decision rests on three concrete reasons, not on pattern preference:

1. **Failure isolation.** A bug or hang in the relay does not touch the API. Users keep enrolling; the outbox accumulates; the relay restarts and drains. In-process background work in the API would couple their lifecycles — relay misbehavior would drag request latency or crash an HTTP-serving worker. Failure-domain separation is the entire point of multi-process designs.
2. **Independent scaling.** API throughput is bound by request volume and DB connections; relay throughput is bound by Kafka publish rate. Different bottlenecks. `FOR UPDATE SKIP LOCKED` was chosen specifically so the relay scales horizontally with zero coordination: `docker compose up --scale relay=3` and each instance gets a disjoint batch.
3. **One persistent Kafka producer.** A long-running process holds a single producer connection for its lifetime — TCP setup, metadata fetch, partition discovery happen once. Inside the API per-request, you would either reconnect each call (wasteful + load on Kafka metadata) or keep a global producer in a "stateless" service (anti-pattern that breaks horizontal scaling). Inside a cron tick, you reconnect every tick.

Fourth, softer reason: it matches the architectural class of the Temporal worker we already run. One more long-running container of an existing shape is operationally free.

**When this approach would be wrong:**

| Situation | Better fit | Why |
|---|---|---|
| Tiny app, ~10 events/day | In-process `BackgroundTask` after commit | A container for that volume is overkill |
| Latency-tolerant batch work | Cron every N minutes | No need for resident process |
| 100k+ events/sec | Debezium / Postgres logical replication | Polling is the wrong shape at that scale |
| No ops bandwidth | Bundle into existing worker | Avoid net-new processes |

We're not in any of those bands.

**"But isn't polling wasteful?"** At our scale, no. A `SELECT ... WHERE sent_at IS NULL LIMIT 100` that returns zero rows every 500 ms is essentially free — Postgres handles thousands of those per second per connection, and the partial index ensures it never scans junk. The "wasteful polling" criticism applies to 10k+ events/sec systems, where you'd switch to push-based via `LISTEN/NOTIFY` or CDC. Not us.

**Signals that would make me revisit the choice:**
1. Outbox accumulating > 10k unsent rows during normal operation → relay is the bottleneck; scale to N replicas first, then CDC.
2. p95 enroll → email latency > 5 s → switch to `LISTEN/NOTIFY` for push-driven wake-ups (eliminates the 500 ms polling floor).
3. Operational pushback on container count → bundle into a Celery beat periodic task; accept tighter coupling for fewer processes.

None of those are firing. The dedicated relay holds its weight.

### Q: What does the `3c8f1b4a9d52` in the Alembic migration filename mean?

**A:** It's an **Alembic revision ID** — a 12-character hex string (48 bits), randomly generated by `alembic revision -m "..."`. Think of it as a git commit SHA, but for the schema.

It's a hex string instead of "v1, v2, v3" for three reasons:

1. **No collision across feature branches.** Two devs each generate a migration without coordinating, no `004` conflict on merge.
2. **No implied total order.** Migration ordering is a linked list, not a sequence — each file declares its `down_revision`. Alembic walks the chain.
3. **Stable identifier.** Renaming the file or its description doesn't change the ID; the DB's `alembic_version` row keeps pointing to it.

The chain in our project right now:

```
1ff633244782   initial_schema             down=None
2a8c1d9e0f1b   add course processed_at    down=1ff633244782
3c8f1b4a9d52   add outbox table           down=2a8c1d9e0f1b
4d9a2c5e7b13   add processed_events       down=3c8f1b4a9d52   ← HEAD
```

The DB tracks the current point with one row:

```sql
SELECT version_num FROM alembic_version;
-- 4d9a2c5e7b13
```

`alembic upgrade head` reads that row, walks the linked list forward, calling each `upgrade()` until it reaches HEAD. `alembic downgrade -1` reverses one step.

### Q: Why do we need Redis when RabbitMQ is already configured for Celery? (broker=RabbitMQ, backend=Redis)

**A:** Celery uses *two* distinct storage concepts that want different access patterns:

| | Broker | Result backend |
|---|---|---|
| Stores | Pending tasks (the queue) | Task state & return values (PENDING / STARTED / SUCCESS / FAILURE) |
| Access pattern | Write once on enqueue, read once on consume, then gone — **queue semantics** | Random lookup by task id — **key-value semantics** |
| Best fit | **RabbitMQ** — durable queues, acks, fair dispatch, DLX | **Redis** — sub-millisecond GETs by key, TTL on results |
| Who writes | The producer (`.delay()`) | The Celery worker (state transitions) |
| Who reads | The Celery worker (pulls tasks) | Callers that want "did this finish?" via `.get()` / `.ready()` |

You **can** use Redis for both, or RabbitMQ for both. People don't, because each is mediocre at the other's job:

- *Redis as broker* — works for small loads, but lacks RabbitMQ's durability semantics (ack timeouts, message TTL, dead-letter exchanges, fair prefetch).
- *RabbitMQ as result backend* — terrible at "show me task abc-123's status" — that becomes queue-scanning gymnastics. Redis does it in one GET.

In our project:
- The broker (RabbitMQ) is **fully used** — every `send_welcome_email.delay(...)` puts a task there, and the Celery worker pulls from it.
- The result backend (Redis) is **barely used today** — we don't call `.get()` anywhere. But Celery insists on initializing the backend client at worker startup (a missing `redis` library is what caused our worker to crash with `ImproperlyConfigured` earlier). And internal Celery features (retry tracking, scheduled-task ETAs, group/chord coordination) do touch it.

Could we drop Redis? Yes, by setting `task_ignore_result=True` and removing the result backend. We don't, because Redis is already in our stack for caching — zero new infra cost — and the day we add a task whose status we want to poll, the backend is already wired.

Shorthand: **RabbitMQ = the inbox of tasks waiting to run. Redis = the filing cabinet of tasks that have run.**

### Q: Does Kafka enqueue tasks into Celery? Does Kafka have that capability? Or does it add to RabbitMQ and then Celery consumes it? What is the "Celery bridge"?

**A:** **No — Kafka does not know about Celery.** Kafka has no concept of tasks, of Celery workers, or of RabbitMQ. The transition from Kafka → Celery happens in *our code*, not by any built-in capability of either system.

The "bridge" is an **informal term** for a process we write — in our case `app/workers/welcome_email_consumer.py`. It is a single Python process that imports both libraries and is the only place in the system where the two worlds touch.

The hop-by-hop reality:

```
Kafka topic events.user.enrolled       ─ raw bytes; Kafka has no opinion on them
   │
   ▼ subscribed by aiokafka
welcome_email_consumer.py              ─ OUR code, running in its own container
   │  - reads the Kafka message
   │  - dedupes via processed_events
   │  - calls send_welcome_email.delay(enrollment_id)   ← THE BRIDGE CALL
   │
   ▼ .delay() is Celery's client API. Internally it publishes an AMQP message
RabbitMQ queue "celery"                ─ Kafka has already forgotten the event
   │
   ▼ long-polled by `celery worker`
celery-worker container                ─ runs the task function, logs, acks
```

The "bridge call" is one line — `send_welcome_email.delay(enrollment_id)` in [welcome_email_consumer.py](../app/workers/welcome_email_consumer.py). Celery's library, behind that call, connects to its broker URL (RabbitMQ in our config) and publishes a task message. The Kafka library and the Celery library don't know about each other; they just happen to be imported in the same process.

**Why this design and not "Celery consumes Kafka directly"?**

| Layer | Optimized for | Tool we use |
|---|---|---|
| Event distribution to multiple consumers | Replayable log, fan-out, ordered partitions | **Kafka** |
| Per-consumer decision to hand off work | Queue semantics, acks, retries, DLX | **RabbitMQ** (Celery's broker) |
| Task execution | Concurrency, time limits, retry policy | **Celery workers** |

Celery is a *queue-based* task framework — its worker model assumes a broker with queue semantics (one consumer pulls, acks, message gone). RabbitMQ and Redis fit. Kafka is *log-based* (many consumer groups read the same message independently; replayable history). Third-party `celery-kafka` libraries exist but force queue semantics onto a log — awkward.

So we keep them separated: Kafka does event distribution, RabbitMQ does task queueing, Celery does task execution. The small Python "bridge" we wrote is the seam between *event distribution* and *task execution*.

If we add a second Kafka consumer later (e.g. an analytics consumer writing to Mongo), it'll be another bridge — and it doesn't have to use Celery at all. Each consumer-group reads the same Kafka topic independently; what they do next is their choice.

### Q: What is the difference between a Celery worker and a Celery broker? RabbitMQ is also called a broker — are they the same thing?

**A:** The word "broker" is used at two levels and that's where the confusion comes from.

**RabbitMQ** = the actual message-broker software running as a container in our stack. It stores messages and delivers them to subscribers. Speaks AMQP. Knows nothing about Python, tasks, or Celery.

**"Celery's broker"** = a Celery *config setting* (`broker=settings.celery_broker_url`) that points at an external broker — in our case, RabbitMQ. Celery doesn't ship its own message storage; it always uses an external one (RabbitMQ, Redis, SQS, etc.). "Celery broker" is shorthand for "the broker Celery is configured to use." It is **not a separate service**.

**Celery worker** = a Python process running `celery worker`. It connects to the broker, pulls task messages, executes them by calling the Python function the task name maps to. In our stack it's the `celery-worker` container.

Mail-room analogy:
- RabbitMQ = **the mailroom** (accepts envelopes, shelves them on labeled racks — the queues).
- Celery worker = **the person** at a desk, walking to the mailroom, picking up envelopes addressed to them, doing the work.
- `.delay()` = **dropping an envelope into the mailroom** (the producer side).

Container-level mapping in our system:

| Service in docker-compose | Role |
|---|---|
| `rabbitmq` | The actual broker — software service, no Python code |
| `welcome-email-consumer` | Producer of tasks (Kafka consumer that calls `.delay()` after dedupe) |
| `celery-worker` | Celery worker (consumer of the RabbitMQ queue) |

Cheat sheet:
- **RabbitMQ** = message-broker software (a container we run).
- **Broker (generic)** = any system that holds messages between producers and consumers — RabbitMQ, Redis, Kafka, SQS.
- **Celery's broker** = config pointing Celery at one of those. In our case → RabbitMQ.
- **Celery worker** = separate Python process pulling tasks from the broker and executing them.

### Q: What is the AMQP protocol?

**A:** AMQP = **Advanced Message Queuing Protocol**. It is a *wire protocol* — a specification for how messages flow over TCP between producers, brokers, and consumers. It is **not software**; it is a contract.

Cleanest analogy: **AMQP is to RabbitMQ what HTTP is to nginx.**

| Layer | Web stack | Messaging stack |
|---|---|---|
| Wire protocol | HTTP | **AMQP** |
| Servers that speak it | nginx, Apache | RabbitMQ, Qpid, ActiveMQ |
| Clients that speak it | curl, axios | py-amqp, Kombu |

A Python producer using `py-amqp` and a Java consumer using a different AMQP client can talk to the same broker because they agree on the wire format. Standardization is the entire point.

The protocol defines a small set of primitives (AMQP 0-9-1 model, which RabbitMQ implements):

| Concept | Role |
|---|---|
| Connection | Persistent TCP socket to the broker |
| Channel | Lightweight session multiplexed inside one connection |
| Exchange | The "switchboard." Producers publish here, never directly to queues. Types: `direct`, `topic`, `fanout`, `headers`. |
| Queue | Message buffer with a name; stores messages until a consumer pulls them |
| Binding | Rule linking a queue to an exchange with a routing key |

Producer publishes to *exchange* → binding routes by key → message lands in *queue* → consumer pulls from queue. Celery hides all of this; one `.delay()` call performs the whole traversal.

In our system the URL `amqp://guest:guest@rabbitmq:5672/` encodes:
- `amqp://` — protocol (unencrypted variant; `amqps://` for AMQP-over-TLS)
- `guest:guest` — credentials
- `rabbitmq` — DNS name of the broker inside the compose network
- `:5672` — standard AMQP port (5671 for TLS; 15672 is RabbitMQ's HTTP management UI)
- trailing `/` — the default vhost (vhost = namespace for partitioning the broker)

Every Celery task message in our system is an AMQP message with:
- *Body* — JSON of `{"task": "tasks.send_welcome_email", "args": [...]}`
- *Properties* — content type, encoding, delivery mode, priority, correlation id
- *Headers* — arbitrary key/value metadata

Live: `open http://localhost:15672` → log in `guest/guest` → Queues → `celery` → Get messages.

**Gotcha:** AMQP 0-9-1 (RabbitMQ's main protocol) and AMQP 1.0 (Apache ActiveMQ, Azure Service Bus) are essentially different protocols sharing the name. We are entirely in 0-9-1 land.

Where each protocol lives in our stack:

| System | Wire protocol | Port |
|---|---|---|
| Postgres | Postgres frontend/backend | 5432 |
| Redis | RESP | 6379 |
| **RabbitMQ** | **AMQP 0-9-1** | **5672** |
| Kafka | Kafka binary | 9092 |
| Temporal | gRPC | 7233 |
| FastAPI | HTTP/1.1 | 8000 |

### Q: What is gRPC, the wire protocol Temporal uses?

**A:** **gRPC = Google Remote Procedure Call.** It is an RPC framework — meaning the developer calls a server-side function *as if* it were a local function, and the framework handles serialization + transport.

Mental model: **gRPC is to Temporal what HTTP/REST is to a typical Node Express API** — a wire protocol for typed function calls over the network. But the implementation differs sharply from REST.

Four layers stacked on top of each other:

| Layer | What it provides |
|---|---|
| Protocol Buffers ("protobuf") | Schema language + compact binary format. ~3–10× smaller than JSON, baked-in schema-evolution rules. |
| Code generation | One `.proto` file → client + server stubs in Python, Go, Java, TypeScript, Rust… |
| HTTP/2 transport | Binary framing, one TCP connection holds many concurrent streams, server push, lower latency than HTTP/1.1. |
| Four streaming patterns | Unary (1↔1), server streaming, client streaming, bidi streaming. |

**Why Temporal specifically chose gRPC:**

1. **Workers long-poll for tasks.** A worker says "give me the next task on `course-publishing`, hold open if there's nothing yet." Server streaming is native to gRPC; clumsy over HTTP/REST.
2. **Polyglot SDKs.** Temporal ships SDKs for Go, Java, Python, TypeScript, .NET, PHP, Ruby — all generated from one `.proto` schema. Identical API across languages because it's literally the same contract.
3. **High-frequency, low-payload RPCs.** Activity heartbeats, workflow state queries, task polls — millions per second on a busy cluster. Protobuf + HTTP/2 is much cheaper than JSON + HTTP/1.1 at scale (binary framing, header compression, connection reuse).

In our system gRPC shows up at:

- `Client.connect("localhost:7233", ...)` in `app/main.py` lifespan — opens the gRPC channel
- `client.start_workflow(...)` in `publish_service.py` — unary gRPC call (StartWorkflowExecution RPC)
- `worker.run()` in `temporal_worker.py` — streaming gRPC calls (PollWorkflowTaskQueue, PollActivityTaskQueue) that long-poll for work
- Temporal UI at `http://localhost:8080` — gRPC-calls the same frontend service the SDK uses

The `temporalio` Python SDK hides every byte of gRPC from our code. We write async Python; the SDK turns it into gRPC traffic.

**REST vs gRPC — when each wins:**

| | HTTP/REST | gRPC |
|---|---|---|
| Payload | JSON (text) | Protobuf (binary) |
| Transport | HTTP/1.1 typically | HTTP/2 |
| Schema | OpenAPI optional, often loose | `.proto` mandatory, strict |
| Typing | Runtime/convention | Compile-time, generated stubs |
| Streaming | SSE/WebSocket bolt-ons | Native, 4 patterns |
| Browser-callable | Yes, directly | Needs gRPC-Web proxy or REST gateway |

Rule: front-of-house (React → FastAPI) → HTTP/REST. Inside the system, between long-lived services with strict typing and streaming needs → gRPC. Hence FastAPI uses HTTP, Temporal uses gRPC.

### Q: How do we know the outbox + Kafka + consumer pipeline actually survives the failures we designed for?

**A:** We ran three stress tests against the live stack and confirmed each failure mode behaves as the design predicted.

**Test 1 — Kafka outage mid-enrollment**
- `docker-compose stop kafka`
- Enrolled a student → API returned **HTTP 201**, unchanged user experience
- Outbox row created with `sent_at = NULL`
- Relay logs filled with `NodeNotReadyError` / `Unable to connect to node 1` but the process did not crash
- After Kafka came back (`docker-compose start kafka`), the relay drained the row in milliseconds; the consumer reconnected, claimed via processed_events, enqueued the Celery task, and the welcome-email log fired (~6s end-to-end including the outage)
- **Verdict:** outbox decouples user-facing work from broker availability. No event was lost; nothing user-visible degraded.

**Test 2 — Duplicate Kafka message injection**
- Inside the `relay` container (which has `aiokafka` installed), ran a Python one-liner that produced a message with an already-processed `event_key` (`enrollment-35c8ab76-…`) and the matching `idempotency_key` header
- The consumer received the duplicate at a new offset, ran `processed_events_repo.claim(...)`, the `INSERT ... ON CONFLICT DO NOTHING RETURNING` returned 0 rows → `claim()` returned False → consumer logged `duplicate enrollment-35c8ab76-… (partition=0, offset=4)` and skipped
- Celery worker received **no new task**; welcome-email log line count stayed unchanged
- **Verdict:** consumer-side dedupe via the `(consumer, event_key)` PRIMARY KEY catches duplicates whether they come from relay retries, Kafka rebalances, or hostile injection.

**Test 3 — Consumer downtime**
- `docker-compose stop welcome-email-consumer`
- Enrolled three students → all returned 201; relay drained all three outbox rows to Kafka (events at offsets 5, 6, 7)
- Consumer-group lag (`kafka-consumer-groups.sh --describe --group welcome-email`): **3** — current offset 5, log-end offset 8
- Welcome-email log count during downtime: unchanged
- `docker-compose start welcome-email-consumer` → consumer rejoined the group at its last committed offset (5), processed messages 5/6/7 in ~5s, advanced to 8
- Welcome-email log count after restart: +3 (one per Crash Tester)
- Lag back to 0
- **Verdict:** Kafka's consumer-group durability means the consumer can be down arbitrarily long without event loss. On restart it resumes exactly where it stopped, processes once each.

Combined, the three tests empirically validate the failure-mode table in the Stage 3 explanation: no event is ever lost, duplicates are absorbed, and every layer can fail independently without the others noticing.

### Q: When emitting `course.published` from a Temporal activity, why did the activity fail with `Unable to bootstrap from [('localhost', 9094, ...)]` even though Kafka was healthy?

**A:** Container-network gotcha. Our `.env` has `KAFKA_BOOTSTRAP_SERVERS=localhost:9094` — the host-mode default, useful when running uvicorn/the worker directly on the host. But inside any compose container, `localhost` is the container itself, not the host machine and not the Kafka container.

The pattern we adopted across the stack: `env_file: .env` brings in the host-mode defaults; `environment:` in each service overrides the URLs with their compose-network names (`postgres`, `redis`, `kafka`, `temporal`). Until we added `course.published` emission, the `worker` service didn't need Kafka — so it never got the override. The activity tried `localhost:9094`, failed, and Temporal kept retrying it forever (which is the correct behaviour — that's why no events were lost; the workflow stayed in "retrying step 4" indefinitely until the env was fixed).

Two takeaways:

1. **Service overrides are per-service.** Adding a new dependency to any single service can require a new `environment:` line — `env_file` defaults aren't always right for in-container life.
2. **Temporal retried for us.** While the env was broken, the workflow sat at attempt 6, 7, 8… on the failing activity. The moment we restarted the worker with the correct env, the next retry succeeded, the activity completed, the workflow advanced, and the message landed on `events.course.published`. No manual replay, no lost work — exactly the at-least-once behaviour Temporal is sold on.

Fix recorded in `docker-compose.yml`:
```yaml
worker:
  environment:
    KAFKA_BOOTSTRAP_SERVERS: kafka:9092   # added — emit_course_published_activity needs Kafka
  depends_on:
    kafka:
      condition: service_healthy           # added — wait for Kafka before starting the worker
```

### Q: What does the observability layer give us, and why do we still need OpenTelemetry + Jaeger on top of Prometheus and logs?

**A:** There are **three pillars of observability**, and they answer different questions:

| Pillar | Tool | Answers | Can't answer alone |
|---|---|---|---|
| Metrics | Prometheus + Grafana | "HOW MANY / HOW FAST / HOW OFTEN" — aggregate numbers over time | "Why was THIS specific request slow?" |
| Logs | structured JSON | "WHAT happened, in full detail" — discrete events | "Which log lines across 6 containers belong to the same request?" |
| Traces | OpenTelemetry + Jaeger | "WHERE did ONE request spend its time, across all services?" | — |

We built metrics + logs. Traces are the missing pillar.

**Why traces matter here specifically:** one enrollment touches five processes and four data stores —

```
[api] enroll → SELECT FOR UPDATE + INSERT enrollment + INSERT outbox  (Postgres)
   (201 returns; rest is async)
[relay] outbox → Kafka
[welcome-email-consumer] Kafka → dedupe (Postgres) → enqueue (RabbitMQ)
[celery-worker] run task → read Postgres → send email
```

If a student says "I enrolled but got no welcome email," debugging *today* means grepping 4 containers' logs and manually stitching the timeline by enrollment_id. Metrics say "p95 is fine"; logs are scattered.

With OpenTelemetry + Jaeger you search one `trace_id` and see the whole waterfall in one screen, with per-span timings — instantly spotting "the celery SMTP span took 240ms and timed out."

**The split** (mirrors Prometheus/Grafana):
- **OpenTelemetry** = the library in your code. Wraps each unit of work in a "span," assigns a `trace_id`, propagates it across service boundaries (HTTP headers, Kafka message headers). Produces the data.
- **Jaeger** = the backend. Receives, stores, and draws the waterfall UI. You never write to it directly.

**The payoff that unifies all three pillars:** the `trace_id` OTel generates is also injected into the structured JSON logs (the reserved `trace_id` field). So: metrics tell you *something* is wrong → traces tell you *where* → logs filtered by trace_id tell you *what* in full detail.

### Q: Why is `configure_json_logging()` called in every worker file instead of once?

**A:** Because **logging configuration is per-process, not per-codebase.**

Each service is a separate OS process in a separate container running a separate Python interpreter:

| container | entry point that calls configure_json_logging |
|---|---|
| api | `app/main.py` (module load) |
| worker | `temporal_worker._run()` |
| relay | `outbox_relay._run()` |
| welcome-email-consumer | `welcome_email_consumer._run()` |
| events-archiver | `events_archiver._run()` |
| celery-worker | `celery_app` `setup_logging` signal |

Python's logging config (root logger handlers + formatters) lives in *that process's memory*. There is no shared global state across processes — different interpreters, different heaps, different containers. Configuring it in `main.py` configures only the API process; the relay process never imports `main.py` (it runs `outbox_relay.py`), so without its own call it would keep Python's default plain-text format.

Key distinction:
- The **logic lives in ONE place** — `app/observability/logging.py`. Not duplicated.
- The **call happens once per process entry point** — because each process configures its own root logger at its own startup.

Same reason each worker opens its own `AsyncSessionLocal`, its own Kafka client, its own Mongo client: you cannot share an open socket, a DB pool, or a configured logger across a process boundary. Each process builds its own resources from shared code. Number of calls = number of processes (6), not number of files. A monolith would call it once; our distributed design calls it six times.

### Q: If OpenTelemetry gives us tracing, why do we also need JSON logs? Is JSON logging just for representation? Is jsonlogger the same as console.log?

**A:** Three sub-questions:

**(a) Logs and traces are different pillars, not redundant.**
- Logs = discrete records of *what happened*, rich free-form detail ("SMTP connection refused", "duplicate skip", "course not found").
- Traces = the *timing + structure* of one request across services (span name + start/end + parent).
- They're complementary: a trace says "the celery span took 240ms and errored" (WHERE); a log says "SMTP connection refused: mailserver down" (WHAT). OTel will never tell you the SMTP detail — that lives in a log line. So logs are the other half, not replaced by tracing.

**(b) JSON is for machine-consumability, not representation.** Plain text is for a human reading one terminal. JSON makes every field indexable so a log aggregator (Loki, Elasticsearch, Datadog, CloudWatch) can run structured queries like `service="celery-worker" AND level="ERROR" AND event_type="user.enrolled"` and alert on them. Today we just print JSON to stdout; the moment a shipper (Promtail/Fluent Bit) is put in front of it, every field is queryable/dashboardable/alertable with **zero code change**. That's the payoff — the format is the investment.

```
container stdout (JSON) → shipper → store (Loki/Elastic) → query (Grafana/Kibana)
```
We're at step 1; steps 2–4 are pure ops config because the logs are already structured.

**(c) jsonlogger is NOT console.log.** In Node terms: `print()` ≈ `console.log` (unstructured). Python `logging` + `python-json-logger` ≈ **Pino/Winston** in JSON mode — a logging *framework* with levels, named loggers, handlers, and a formatter that emits structured JSON. `jsonlogger.JsonFormatter` turns each `logger.info(...)` record into a JSON object instead of a string.

**The complete footprints of one enrollment** (enrollment id 999):

| Step | Process | Metric fired | JSON log | Trace span (future) |
|---|---|---|---|---|
| 1 | api | http_requests_total +1, events_emitted_total{user.enrolled} +1 | uvicorn.access 201 | `POST /enroll` + db child spans |
| 2 | relay | outbox_published_total +1 | "published 1 events" | `relay.publish` |
| 3 | welcome-email-consumer | events_consumed_total{outcome=enqueued} +1 | "enqueued enrollment-999" | `consumer.handle` |
| 4 | celery-worker | celery task +1 | "welcome-email → alice@…" | `celery.send_welcome_email` |

- **Metrics** answer aggregate health across all enrollments.
- **Logs** let you find each individual line and filter by field.
- **Traces** (not built yet) tie all four steps into ONE waterfall via a shared `trace_id`, propagated through the outbox row and the Kafka message header. Today, correlating Alice's enrollment means grepping `enrollment-999` across 4 containers; with OTel you search one `trace_id` and the whole causal chain lights up — and that same `trace_id` appears in every JSON log line, unifying all three pillars. The empty `trace_id` field in app/observability/logging.py is the hook waiting for the OTel chunk to populate.

### Q: For metrics, do we `+1` on every event? Is there a queue for metrics?

**A:** No queue — and that's the key difference between events and metrics.

| | Events (user.enrolled …) | Metrics (counters) |
|---|---|---|
| Transport | Pushed through queues (outbox → Kafka → RabbitMQ) | Pulled — Prometheus scrapes /metrics |
| Queue? | Yes | **No queue at all** |
| Storage | Durable (Postgres → Kafka → Mongo) | In-memory number in the process |
| Lose one? | Never acceptable | Fine — next scrape has the current total |
| Cost each | DB write + network | `+1` in RAM (nanoseconds) |

**Two kinds of metric:**
- *Auto-instrumented* (prometheus-fastapi-instrumentator): middleware bumps `http_requests_total` / `http_request_duration_seconds` on every request. We write zero `+1` code.
- *Custom business counters*: we DO call `.inc()` manually, e.g. `events_emitted_total.labels(event_type=..., path="outbox").inc()` in `event_service.emit()`. But `.inc()` is just `number += 1` in process RAM — not a network call, not a queue push. That's why it's cheap to do per event.

**What actually happens:** the counter is a labelled set of numbers in the process's memory. `.inc()` bumps the number locally. Nothing leaves the process. Then Prometheus, on its own 10s timer, HTTP-GETs `/metrics`, the app renders the current totals as text, and Prometheus stores them as time-series points with a timestamp. Over time it builds a graph; `rate(counter[1m])` computes the per-second slope.

```
app RAM: counter += 1   ──HTTP GET /metrics every 10s──►  Prometheus stores snapshots
   (push? NO)                                              (pull, on a timer)
```

**Counter resets:** counters live in process memory, so they reset to 0 on restart. That's expected — you query `rate(counter[5m])`, not the raw value, and Prometheus's `rate()` detects resets and handles them. The slope is what matters, not the absolute number.

**Why pull-no-queue for metrics:** a metric is cheap to recompute (just the current counter), and missing a scrape is harmless because counters are cumulative. An *event*, by contrast, is a discrete fact that must not be lost — hence the durable outbox + Kafka. Different reliability needs → different transport.

### Q: Where do logs, metrics, and traces get stored? Is observability data kept in our application DB?

**A:** No — none of it goes in Postgres or Mongo. Each observability signal has its own dedicated, purpose-built store:

| Signal | Stored by | Location (our setup) | In app DB? |
|---|---|---|---|
| Metrics | Prometheus TSDB | `prometheus_data` volume (`/prometheus`), 15-day retention | No |
| Logs (now) | Docker `json-file` log driver | files on the Docker host; read via `docker-compose logs` | No |
| Traces (Jaeger, later) | Jaeger's own backend | in-memory/Badger dev; Cassandra/Elasticsearch prod | No |
| Grafana dashboards/users | Grafana config DB | `grafana_data` volume (SQLite) — config only, not the metrics | No |

**The subtle trap:** the Mongo `events` collection IS in our DB — but it's *application data* (business facts like "Alice enrolled", queried by /admin/metrics, kept forever), NOT observability data. The JSON stdout logs are operational records of the *system* doing work (read via `docker logs`, on host disk, eventually rotated). Both involve "events" and "JSON" but are different concerns.

**Why observability is deliberately kept OUT of the app DB:**
1. Volume — millions of log lines / metric samples per day would bloat Postgres and slow transactional queries.
2. Wrong shape — metrics are time-series, logs need full-text search, traces are span trees; relational tables are bad at all three; specialized stores are 10–100× more efficient.
3. Blast-radius isolation — a logging spike filling observability storage must not take down the DB enrollments depend on.
4. Retention & criticality differ — metrics ~15d, logs ~7–30d, enrollments forever; losing metrics is an inconvenience, losing an enrollment is a bug.

**Dev vs prod:**
```
DEV:   metrics→Prometheus container; logs→stdout→Docker json-file; traces→(none yet); dashboards→Grafana container
PROD:  metrics→Prometheus/Grafana Cloud/Datadog; logs→shipper(Promtail/Fluent Bit)→Loki/Elastic/CloudWatch;
       traces→OTel→Jaeger/Tempo/Datadog; dashboards→Grafana
```
Logs are JSON precisely so the prod step is config, not code — point a shipper at stdout and every field is indexed. This follows the 12-factor rule: the app writes to stdout and the platform handles storage/routing.

**Dev caveat:** Docker's default json-file driver has no rotation in our compose, so container logs grow unbounded over long runs. For a long-lived setup add `logging: {driver: json-file, options: {max-size: 10m, max-file: 3}}` per service, or ship logs off-host.

### Q: How is OpenTelemetry + Jaeger wired in, and what's the current scope of tracing?

**A:** Setup mirrors the logging setup — `configure_tracing(service_name)` in `app/observability/tracing.py`, called once per process (api lifespan + each worker `_run()` + the celery setup signal). It builds a `TracerProvider` with an OTLP/gRPC exporter pointed at `OTEL_EXPORTER_OTLP_ENDPOINT` (set to `http://jaeger:4317` per service in docker-compose; empty → disabled for host dev). Auto-instrumentation:
- `FastAPIInstrumentor` — one span per HTTP request (health/metrics excluded)
- `SQLAlchemyInstrumentor` on `engine.sync_engine` — a child span per SQL statement

Jaeger runs as `jaegertracing/all-in-one` with `COLLECTOR_OTLP_ENABLED=true`; UI at http://localhost:16686, OTLP receivers on 4317 (gRPC) / 4318 (HTTP).

**Logs↔traces bridge:** a `_TraceContextFilter` in `app/observability/logging.py` reads the active span context and stamps `trace_id` + `span_id` onto every log record, so the JSON logs carry the same `trace_id` Jaeger shows. Verified: an enroll request's HTTP log line and its SQL COMMIT log line share one `trace_id` (different `span_id`s).

**Verified working:** a single `POST /enroll` produced an 8-span trace in Jaeger whose waterfall maps exactly to the code — `POST /enroll` → connect → SELECT (course FOR UPDATE) → SELECT (capacity) → INSERT (enrollment) → INSERT (outbox) → http send. You can literally see the outbox INSERT inside the same request as the enrollment INSERT (the atomicity, visualized). Five services report to Jaeger: api, outbox-relay, events-archiver, temporal-worker, welcome-email-consumer.

**Current scope vs the "follow one request across services" ideal:** today each service produces its OWN traces, and *within* the API the request→DB path is one linked trace. The async event pipeline (API → outbox → relay → Kafka → consumer → Celery) is NOT yet stitched into a single cross-service trace. Doing that needs trace-context propagation across the async boundary:
1. In `event_service.emit`, inject the current `traceparent` (W3C TraceContext) into the outbox row (new column or payload metadata).
2. The relay reads `traceparent` and sets it as a Kafka message header.
3. The consumer extracts the header and starts its span with that remote context as parent (or as a span link, which is the more correct primitive for async/queue boundaries).
4. Propagate again into the Celery task headers.

This is a known, documented extension — the synchronous-path tracing already meets the Week 3 "basic tracing available" bar; cross-async-boundary propagation is an enhancement (and is genuinely subtle — production systems often use span *links* rather than parent-child for queue hops, because the consumer runs much later and isn't a synchronous child).

### Q: How does the observability stack wire up, file by file? (Prometheus + Grafana, JSON logs, OpenTelemetry + Jaeger)

**A:** Note two different "observability" directories: `app/observability/` is **Python code** that runs inside each process; `observability/` (no `app/`) is **infra config** mounted into the off-the-shelf Prometheus/Grafana containers. They never import each other.

**Prometheus + Grafana**
- `app/observability/metrics.py` — defines custom counters (importing it registers them at value 0).
- `app/services/event_service.py` — the one place that `.inc()`s `events_emitted_total`.
- `app/main.py` — `Instrumentator().instrument(app).expose(app,"/metrics")`: middleware auto-records HTTP metrics; `/metrics` renders the whole registry as text.
- `observability/prometheus.yml` — scrape job: GET `api:8000/metrics` every 10s.
- `observability/grafana/provisioning/datasources/prometheus.yml` — auto-adds Prometheus as a data source.
- `observability/grafana/provisioning/dashboards/dashboards.yml` — load dashboards from a dir.
- `observability/grafana/dashboards/smartcourse.json` — the panels (PromQL).
- `docker-compose.yml` — runs prometheus + grafana, mounts the configs.
- Runtime: app keeps counters in RAM → `/metrics` renders them → Prometheus PULLS every 10s → TSDB → Grafana queries Prometheus → panels.

**Structured JSON logs**
- `app/observability/logging.py` — `_JsonFormatter` (record→JSON), `_TraceContextFilter` (stamps trace_id/span_id), `configure_json_logging(service_name)` (swaps root handler, forces uvicorn/celery loggers to propagate).
- Called once per process: api in `main.py`; each worker in its `_run()`; celery via the `setup_logging` signal. Six processes, six calls, one implementation.
- Runtime: `logger.info()` → root handler → filter adds trace_id → formatter renders JSON → stdout → Docker json-file (→ Loki/Datadog in prod). No DB, no network.

**OpenTelemetry + Jaeger**
- `app/observability/tracing.py` — `configure_tracing()` (TracerProvider + BatchSpanProcessor + OTLPSpanExporter→jaeger:4317; no-ops if endpoint empty), `instrument_fastapi(app)` (span per request), `instrument_sqlalchemy(engine.sync_engine)` (child span per query).
- `app/config.py` — `otel_exporter_otlp_endpoint` ("" = disabled).
- `app/observability/logging.py` `_TraceContextFilter` — the bridge: reads the active span's trace_id and writes it on every log record.
- `app/main.py` + each worker — call `configure_tracing` + instrument helpers (order: configure first, then instrument).
- `docker-compose.yml` — `jaeger` service (OTLP enabled, UI 16686); `OTEL_EXPORTER_OTLP_ENDPOINT: http://jaeger:4317` on all 6 app services; `.env` empty default for host dev.
- Runtime: request → FastAPIInstrumentor opens span (trace_id) → SQLAlchemyInstrumentor adds DB child spans → BatchSpanProcessor → OTLP gRPC → Jaeger stores + renders waterfall.

The thread tying all three: the same `trace_id` appears in the trace (Jaeger) and on every log line (stdout) for that request.

### Q: If we have JSON logs filterable by user_id (and can put logs in Grafana), why do we need tracing? And don't we still have to find a trace_id first?

**A:** A log is a *flat list of events*; a trace is a *timed tree*. Filtering logs by user_id gives "the events for X in time order" — genuinely most of "what happened to this user." What it can't cheaply give:

1. **Causal structure** — logs don't encode "this SQL ran because of this call because of this request"; you infer it from timestamps, which breaks down under concurrent interleaving. A trace encodes parent→child explicitly.
2. **Per-step latency, free** — a span has start+end+duration as first-class data. From logs you'd have to log before/after every operation and subtract by hand. Traces give the waterfall automatically.
3. **Finding the bad requests without an id** — see below.

Example: *"p95 jumped 600ms→3s, why?"* Logs by user_id: pick one user, eyeball timestamps, can't easily see which step or aggregate across all slow ones. Traces: filter `duration>2s`, open one, see `SELECT … FOR UPDATE` went 5ms→2.8s = lock contention. 30s vs an hour.

**"Still have to find trace_id first?"** No — you discover it by filtering on symptoms, you don't hunt for it. The flow is: METRICS alert (something's wrong, no id) → TRACES filtered by symptom like `duration>2s` or `status=500` (returns the bad requests — this is what logs can't do) → open the waterfall, find the slow span → grab its trace_id → pull logs by trace_id for full detail. metric→trace→log; trace_id is the handoff token between "where" and "what", discovered not hunted.

**"We can attach logs to Grafana."** Yes — Grafana + Loki, and the modern setup is metrics+logs+traces all in Grafana. But that's logs in a nicer viewer, not logs doing what traces do. Grafana's killer feature is *linking*: a log line's trace_id becomes a click-through to the trace and back — which only works because trace_id is in both (why we stamp it on the JSON logs). It reinforces the case for tracing, doesn't replace it.

**Honest scale caveat:** at SmartCourse's size, structured logs + metrics would get you through most debugging; tracing's marginal value grows with number of services per request, concurrent volume, and latency-sensitivity. We built it for the free latency waterfall (logs can't give it cheaply) and to demonstrate the production pattern. Right tool per question: metrics detect, traces localize, logs explain.

### Q: Is tracing basically "total time across services"? Doesn't Prometheus already time each request? Is a trace a stack of layers?

**A:** Three clarifications:

**Tracing = one request's total time PLUS its decomposition.** Not an aggregate across everything — it's ONE request, broken down: total duration (root span) + each step's slice (child spans) + structure (which called which, sequential vs parallel). It captures both time *between* services (the hops) and time *within* a service (the DB query inside the API).

**Prometheus DOES time requests — but only in aggregate, never decomposed.** `http_request_duration_seconds` takes one number per request (its total), drops it in a histogram, and shows the distribution across ALL requests ("p95 of all /enroll = 600ms"). It retains no individual request and no breakdown of where the 600ms went. Tracing captures every step of an individual request. Analogy: Prometheus = monthly fitness stats ("avg pace 6min/km, slowest 9"); tracing = GPS of one specific run ("km3 was 9min — traffic light here"). Prometheus says something's off; tracing says which segment. So: **Prometheus = overall health + aggregate timing; tracing = per-request decomposition.**

**A trace is a tree of timed spans, drawn as a nested waterfall** — yes, "stacking of layers" is right. Each span is a bar (start position + length); children nest under their parent; overlapping bars = concurrent, sequential bars = one-after-another. It's a tree (children can have children, e.g. a downstream service's spans nest deeper), not just flat layers. Our enroll trace: root `POST /enroll` (10ms) contains child spans connect / SELECT / SELECT / INSERT / INSERT / http-send, each a slice of the 10ms. Prometheus measures the whole bar's length across all requests; tracing shows the stack inside one bar.

### Q: Is Jaeger shown in Grafana? Have we added Loki? Can we see logs inside Jaeger?

**A:** **Jaeger in Grafana — yes, now added.** `observability/grafana/provisioning/datasources/jaeger.yml` registers a Jaeger datasource (`url: http://jaeger:16686`); after a Grafana restart, Grafana → Explore → "Jaeger" datasource queries traces. Verified by proxying `GET /api/datasources/proxy/uid/jaeger/api/services` through Grafana — returned all 6 services. (Grafana's generic `/health` endpoint returns "Plugin unavailable" 500 for the Jaeger plugin — a known quirk; the proxy proves the datasource works.)

**Loki — NOT added.** Logs still go stdout → Docker json-file driver → `docker-compose logs`. They are not in Grafana. To get them there: add a `loki` service + a shipper (Promtail/Alloy/Fluent Bit tailing container stdout) + a Loki datasource. Then Grafana links a log's `trace_id` to its trace.

**Can Jaeger show our logs? No — common misconception.** Jaeger stores spans + span-level tags/events (e.g. an exception event on an errored span). It does NOT store application `logger.info(...)` stdout logs — those never go to Jaeger; only the tracing exporter's spans do. So Jaeger = traces (+ span events), not a log viewer. Seeing logs next to a trace requires a log store (Loki/Elastic) and Grafana linking via the shared `trace_id`.

### Q: What changes between our current all-in-Docker setup and production?

**A:** Headline: **the application image does not change** — the same `smart-course-app` image runs in prod. What changes is everything around it.

1. **Orchestration:** docker-compose (single host, manual) → Kubernetes/ECS/Nomad (multi-host scheduling, self-healing, rolling deploys, autoscaling). Healthchecks → k8s readiness/liveness probes; services → Deployments; the `migrate` one-shot → a pre-deploy Job/init-container.

2. **Stateful infra → managed, not plain containers:** Postgres → RDS/Cloud SQL/Aurora (backups, PITR, primary+replicas, failover); Kafka (we run 1 broker, RF 1) → MSK/Confluent/Redpanda with ≥3 brokers and RF≥3 (RF 1 = data loss on one node death); Redis → ElastiCache; Mongo → Atlas; RabbitMQ → CloudAMQP/operator; Temporal all-in-one → Temporal Cloud or a real cluster. You don't run source-of-truth stores as ephemeral containers.

3. **Strip dev conveniences:** `uvicorn --reload` + `./app` bind-mount → `gunicorn -w 4 -k uvicorn.workers.UvicornWorker`, code baked into the image; `watchfiles` wrappers → plain `python -m`; remove mongo-express/kafka-ui/Grafana admin-admin/anonymous access; `KAFKA_AUTO_CREATE_TOPICS_ENABLE` off, topics created explicitly with partitions + RF.

4. **Secrets & config:** `.env` plaintext SECRET_KEY/passwords → secrets manager (Vault/AWS Secrets Manager/k8s Secrets); per-service env injected by the orchestrator pointing at managed endpoints.

5. **Scaling & networking:** API + workers run N replicas (Kafka consumer groups partition automatically; relay's FOR UPDATE SKIP LOCKED makes multi-relay safe); only the ingress (API+frontend) is public, everything else on the private network (today all on localhost ports); TLS everywhere (https, amqps, Kafka SASL/TLS, Mongo TLS).

6. **Observability hardening:** Prometheus 1-container + static targets → HA Prometheus/Thanos/Mimir or managed, with service discovery + long-term storage; logs stdout (no rotation!) → shipper → Loki/Elastic/CloudWatch with retention; Jaeger all-in-one in-memory (traces lost on restart) → Jaeger with Cassandra/ES backend or Grafana Tempo, plus sampling; Grafana admin/admin → SSO. (Provisioned dashboards/datasources already carry over.)

7. **CI/CD & frontend:** build image in CI → registry → deploy via pipeline/GitOps, migrations as a gated step; frontend `npm run dev` (Vite dev server) → `npm run build` → static files on CDN/object storage/nginx.

What's already prod-shaped and carries over unchanged: the layered app, one-image-many-roles design, healthchecks, provisioned Grafana, structured JSON logs, and the outbox/idempotency/dedupe correctness. The work is mostly platform (k8s + managed infra + secrets + TLS), not application rewrite.

### Q: Can we see traces in Grafana the same as in Jaeger? And we added Loki — what's the full picture now?

**A:** **Traces in Grafana = same data, different front-end.** With the Jaeger datasource added, Grafana → Explore → Jaeger renders the identical waterfall (same spans, timings, tags) because it queries the same Jaeger backend. The value isn't different data — it's the unified pane + cross-signal linking. Jaeger's native UI keeps a few trace-specialist extras (service dependency graph, trace compare); for reading a trace they're equivalent.

**Loki — now added**, completing the logs pillar in Grafana:
- `loki` service (single-binary, built-in default config) + `promtail` service (tails every container's stdout via the Docker socket using `docker_sd_configs`, ships JSON lines to Loki).
- `observability/promtail.yml` — docker service-discovery; labels streams by `container`. Only needs the Docker socket mounted (no host log-file paths → works on Docker Desktop).
- `observability/grafana/provisioning/datasources/loki.yml` — Loki datasource WITH a `derivedFields` entry: a regex pulls `trace_id` out of each JSON log line and turns it into a clickable link to the Jaeger datasource. That's the logs→traces click-through.

**Verified end-to-end after a 6-lifecycle traffic burst:**
- Prometheus: events_emitted, request rate, p95 all populated.
- Jaeger: latest enroll trace = 8 spans.
- Loki: thousands of log lines across all 5 app containers; queryable via the Loki API and through the Grafana datasource proxy.
- A real log line carried `trace_id: f0c756f5…` — so the derived-field link has something to match.
- Mongo: 23 user.enrolled / 16 course.published / 15 lesson.completed.

**The full single-pane-of-glass is now live in Grafana:** metrics (Prometheus) + logs (Loki) + traces (Jaeger), tied together by `trace_id` — from a log line you can jump to its trace; metrics tell you something's wrong, the trace localizes it, the log explains it. (Note: Promtail is in LTS; Grafana now steers new setups to Alloy — same role, different agent.)

**Counter-vs-store nuance observed:** Prometheus `events_emitted_total` showed 13 while Mongo had 23 user.enrolled. Not a bug — the Prometheus counter is in-memory and resets on API restart (counts emits since the process started; also only counts the outbox-path emits from the API, not the Temporal-direct course.published), whereas Mongo accumulates every event ever archived. Different lifecycles: metrics = current-process cumulative (queried via rate()), event log = permanent.

### Q: When something goes wrong, where do I look first? What are realistic use cases to practice the observability stack?

**A:** Pick the first tool by what you *already know*:

| You know | Start with | Why |
|---|---|---|
| Aggregate / numbers look off | METRICS (Prometheus/Grafana) | Aggregate detection — find the affected requests |
| The specific user/entity | LOGS (Loki by id) or Mongo events | Per-entity narrative |
| A workflow is stuck | Temporal UI | Specialized state visualization |
| An event isn't moving | Kafka UI (consumer lag) → RabbitMQ (queue depth) → consumer/Celery logs | Pipeline-stage isolation |
| Things look broken overall | `docker-compose ps` + container logs | Start from health |

**Drill direction:** metrics → trace → log. Metrics tell you *something* is wrong (no id needed). Traces filtered by symptom (`duration>2s`, `status=500`) tell you *where* — and give you a trace_id. Logs filtered by that trace_id tell you *what* in full detail. You discover the trace_id, you don't hunt for it.

**Five reproducible use cases:**

1. **"Welcome email never arrived"** — `docker-compose stop celery-worker` then enroll. Mongo events shows the enrollment (request layer worked); welcome-email-consumer logs show `enqueued` (consumer worked); RabbitMQ UI shows the `celery` queue depth > 0 (task waiting); starting celery-worker drains it. Lesson: the pipeline is layered; debugging = find the FIRST broken hop.

2. **"Publish stuck"** — `docker-compose stop worker` then POST /publish. Temporal UI shows workflow `Running` with activity scheduled but never started → worker not polling. `docker-compose start worker` → activity picked up, workflow advances. Lesson: workflow engines visualize stuck state; don't grep logs first.

3. **"Show me everything Alice did today"** — `SELECT id FROM users WHERE email='alice@…';` → `db.events.find({"payload.student_id": "<uuid>"}).sort({archived_at:1})` → chronological event list. Pick one event → `{container="smart-course-api-1"} |= "<event_key>"` in Loki → see the request → click the trace_id → see the waterfall in Jaeger. Lesson: the Mongo `events` collection is the user activity log; Postgres = current state, Mongo = history.

4. **"/enroll is slow"** — Reproduce by 5 concurrent enrolls against the same course (lock contention on SELECT FOR UPDATE). Grafana → Prometheus p95 per handler. Grafana → Jaeger → filter traces `duration > 1s` → open one → see the SELECT FOR UPDATE span dominates. Filter logs by trace_id → confirms lock wait. Lesson: metric → trace → log is the canonical drill-down.

5. **"Duplicate event in the system"** — Reproduce by re-publishing a Kafka message with an existing `event_key` (one-liner from inside the relay container). welcome-email-consumer logs show `duplicate enrollment-…`; Mongo `countDocuments({event_key})` stays at 1; no new welcome email log. Lesson: idempotency + dedupe ledger work silently — when everything's fine, you see nothing happen.

**Practical setup note (encountered live):**
- Loki/Promtail can be flaky on fresh start (Promtail saw `"at least 1 live replicas required, could only find 0 unhealthy instances"` and held writes). Fix: `docker-compose restart loki promtail`, then wait ~10s for the ingester to come ready. The `label/container/values` endpoint is a quick health check — all 20 containers should appear.
- In Grafana Explore, the **time picker (top-right)** is the most common reason a Loki query returns empty. Default is often "Last 1 hour"; widen it to "Last 24 hours" or use absolute timestamps before debugging the query itself.

### Q: Why can students not see any lesson content — no text, no video, no link — in the UI?

**A:** Both layers contribute to the gap:

**Backend.** The `lessons` table has `content_type` (video/text/pdf) and `content_url` (external link) — but **no `content_text` column**. Text lessons can only point at a URL, which we flagged earlier as the design flaw to fix (forcing the one natively-text content type through a URL). The seed mock generator created lessons WITHOUT a `content_url` at all — just `{title, order_index, content_type:"text"}` — so there's literally no content reference of any kind.

**Frontend.** `LessonList.tsx` renders title + content_type + duration + an "Open" link *only if* `content_url` is set. So:
- No URL → just title metadata, nothing to consume.
- With URL → still just a link out, never an inline render (no embedded YouTube iframe for video, no PDF embed, no markdown render for text).

**Fix (three small chunks):**
1. Backend: add `content_text TEXT NULL` column (model + schema + Alembic migration); accept it in `LessonCreate`. Lessons of type `text` use this column; `video`/`pdf` continue using `content_url`.
2. Frontend: a real "lesson player" that switches on `content_type` — text → render `content_text` (markdown-formatted), video → embed YouTube/Vimeo iframe (or `<video>` for direct URLs), pdf → `<iframe>` embed or download card.
3. Seed: update the mock generator with real content (short markdown body for text lessons; real YouTube tutorial URLs for video lessons; a public PDF URL for pdf lessons).

### Q: For Week 4, what's a chunk, what's an embedding, and how is the data divided?

**A:** Three layers stacked:

**Chunk** = a small piece of source text (200–500 words) that becomes one searchable unit. We chunk instead of storing whole lessons because (1) precision — return the paragraph about replication lag, not the whole lesson; (2) LLM context window — chunks fit in prompts; (3) embedding quality — focused text produces meaningful vectors.

**Embedding** = a list of numbers (a vector — 384 dims for `all-MiniLM-L6-v2`) representing the *meaning* of a piece of text. The model was trained so semantically similar texts produce nearby vectors (small cosine distance). That single property turns "find similar text" into "find nearby vectors" — a SQL `ORDER BY embedding <=> $query_vec LIMIT N` in pgvector. It works for meaning, not keywords: "scaling Postgres" can match a chunk that says "handling high write throughput."

**Data division — three layers top to bottom:**
- Course (publish event triggers the pipeline)
- Lesson (one row in `lessons`)
- Chunks (N rows in `lesson_chunks`, each with FK to the lesson, an `order_index`, and a `vector(384)` column)

Chunks belong to ONE lesson and never span lessons — so retrieval can filter `WHERE course_id = ...` and each result shows "this came from Lesson 1.2." Chunking rule: ~400 tokens per chunk, ~50-token overlap, sentence-boundary-aware. Overlap matters because answers near a chunk boundary would otherwise split in two and lose context.

**The full pipeline (Week 4):**

INGESTION (once, when a course is published, inside the Temporal `process_lessons_activity` we currently have stubbed):
1. EXTRACT text — text → `content_text` directly; video → faster-whisper transcript; pdf → pypdf
2. CHUNK — split into ~400-token chunks with overlap
3. EMBED — `sentence-transformers` produces a 384-d vector per chunk
4. STORE — bulk INSERT into `lesson_chunks(lesson_id, course_id, chunk_index, text, embedding)`

RETRIEVAL (every search):
1. Embed the query → query vector
2. `SELECT text, lesson_id FROM lesson_chunks ORDER BY embedding <=> $vec LIMIT 5`
3. Return top-K chunks with their lesson context

In Week 5 those chunks feed an LLM prompt for RAG Q&A.

**Where each piece lives:**
- Raw text source: `lessons.content_text` (text) or fetched from `content_url` (video/pdf)
- Chunks + embeddings: new `lesson_chunks` table in Postgres with the pgvector extension
- Chunker: `app/services/chunking_service.py` (pure Python)
- Embedder: `app/services/embedding_service.py` (wraps sentence-transformers, model loaded once per process)
- Orchestrator: `app/temporal/activities/course_publish.py` — replace the `process_lessons_activity` stub with extract → chunk → embed → bulk insert
- Retrieval API: `app/routers/search.py` → `POST /api/v1/search/semantic`
- UI: a search box on the Course Detail page

**Chunking unit decision: tokens (via `tiktoken`), sentence-boundary aware.** Characters are too crude (split mid-word), word counts are imprecise against LLM context limits, tokens match what the Week 5 LLM cares about. 400 tokens + 50-token overlap is the recommended default.

### Q: How does dual-source lesson content (URL or upload) + the extraction cache work?

**A:** A video/pdf lesson resolves an **effective source**: `storage_key` (uploaded to our object store) wins over `content_url` (external link). Both feed the same chunking + playback machinery. Text lessons use `content_text` inline. Keeping the URL option means no migration pain for existing lessons and matches real LMSs (paste a YouTube link OR upload an MP4).

**Object storage = MinIO (dev) / R2 / S3 (prod).** Same boto3 code; swap is env-vars only. The key Docker subtlety — a presigned URL embeds the host it's signed for:
- Browser-facing (upload PUT, playback GET) → presigned against the **public** endpoint `localhost:9000`.
- Worker-facing (download for Whisper/pypdf) → **direct `get_object`** against the **internal** endpoint `minio:9000`, no presign.
`storage_service.py` keeps two boto3 clients for exactly this.

**Upload flow** (bytes never touch our API): browser → `POST /api/v1/uploads` → presigned PUT URL + `storage_key` → browser PUTs file straight to MinIO → `storage_key` sent in `LessonCreate`. `LessonResponse.playback_url` is a presigned GET (uploads) or the external URL.

**Extraction cache** (`cached_text` + `cached_text_source`): on publish, video/pdf text is memoised on the lesson keyed by a source fingerprint (`storage:<key>` or `url:<url>`). A re-publish with an unchanged source is a **cache hit** — skips Whisper/pypdf entirely. Write-back happens on the ORM object in the activity's session, so it commits with the activity.

**Verified E2E:** uploaded a PDF → presigned PUT (HTTP 200) → lesson with storage_key → playback_url presigned → publish → worker `get_bytes` from MinIO → pypdf extract → 1 chunk in pgvector → `cached_text` populated → re-publish logged `extraction cache hit for lesson=…` (no re-extraction).

**Files:** `storage_service.py`, `routers/uploads.py`, `lesson_service.effective_source/source_fingerprint/playback_url/to_response`, `extraction_service.{extract_pdf_bytes,transcribe_bytes}`, activity `_lesson_text` (cache + storage), migration `7a1c5d9e2f04`, compose `minio` service, frontend `api/uploads.ts` + `ModuleManager` URL/Upload toggle + `LessonPlayer` playback_url.

### Q: What config goes in .env vs YAML? Does Kubernetes have any role locally? What do we maintain for production?

**A:** The governing principle is **12-factor**: code is identical across environments; only config differs. That splits everything into three buckets:

| Bucket | What | Dev location | Prod location |
|---|---|---|---|
| Secrets | passwords, API keys, JWT secret | `.env` (gitignored) | secrets manager → k8s Secret |
| Per-env values | hostnames, endpoints, URLs, toggles | `.env` + compose `environment:` | ConfigMap / Secret |
| Topology | which services exist, ports, wiring, volumes | `docker-compose.yml` | k8s manifests |

**The test for "env var vs YAML":** *does this value change between laptop / staging / prod?* Yes → env var. No → it's structure, lives in YAML (`ports: 8000`, `image: pgvector/pgvector:pg15`, `worker depends_on kafka`).

**Does k8s run locally? No.** docker-compose IS our local orchestrator. k8s is purely a production concern. You *can* run k8s locally (kind/minikube/k3d) but it adds complexity without teaching anything compose doesn't — skip it for this project. Same Docker image runs in both; only the orchestration layer differs.

**What we maintain for production** (`deploy/k8s/`):
- Stateful infra (Postgres, Kafka, Redis, RabbitMQ, Mongo, Temporal, object storage, observability) is **managed services in prod, NOT in-cluster** — running stateful systems on k8s is an operational burden managed services solve better. k8s runs only our stateless code.
- Manifests: `namespace`, `configmap` (non-secret per-env), `secret.example` (template — real one from secrets manager), `migrate-job` (one-shot, gated before rollout), Deployments for api (gunicorn+uvicorn, 3 replicas) / worker / relay / welcome-email-consumer / events-archiver / celery-worker, `api-service`, `ingress` (TLS, only the API is public).
- Workers scale horizontally safely: Kafka consumer-group partitioning, relay's `FOR UPDATE SKIP LOCKED`, Temporal activity distribution.
- Not a Helm chart yet — plain manifests are clearer for review; Helm/Kustomize is the next step for multi-env value overrides.

**Config cleanup done this session:** moved the last hardcoded secrets (MinIO `minioadmin`, Grafana `admin`, S3 creds) out of docker-compose into `.env` via `${...}` substitution; rewrote `.env.example` as a documented template with `# CHANGE IN PROD` markers on every secret + managed-endpoint value. Zero hardcoded credentials remain in docker-compose.yml.

### Q: Does video upload actually work end-to-end (Whisper on an uploaded file)?

**A:** Verified. Uploaded a 2.8MB mp4 → presigned PUT to MinIO (HTTP 200) → lesson with storage_key → publish → Temporal worker `get_bytes` from MinIO → ffmpeg decode → faster-whisper ran (`"Processing audio with duration 00:05.759"`). The storage→Whisper path is fully functional. The test clip had no speech (Whisper detected language 'nn' at 0.38 = noise) so produced an empty transcript → 0 chunks, which is *correct* behaviour, not a bug. A separate corrupt 167-byte file was handled gracefully (`"Invalid data found when processing input"` → warning logged, workflow still succeeded). So: upload + storage + extraction + error-handling all proven; a speech-bearing clip would simply yield transcript text → chunks.

### Q: How many k8s "services" did we create, do they need separate AWS instances, and where do managed-service connection variables live?

**A:** Two distinct categories — only the first is in `deploy/k8s/`:

**Category A — our stateless code (6 Deployments + Job + Service + Ingress):** api (3 replicas), worker (2), relay (2), welcome-email-consumer (2), events-archiver (2), celery-worker (2) — 13 pods, all the same image, different commands. **They do NOT each get a server.** k8s bin-packs all 13 pods onto a *shared* EKS node group (~3 EC2 instances, autoscaled). HPAs (`hpa.yaml`) add pods on CPU; the cluster autoscaler adds EC2 nodes when pods don't fit. You never pin a service to an instance.

**Category B — stateful infra (NOT in k8s — managed AWS services):** each IS its own managed service, but AWS runs the underlying instances:

| dev container | AWS managed | own instance? |
|---|---|---|
| api/worker/relay/consumers/celery | EKS pods on shared EC2 node group | no — packed |
| postgres (pgvector) | RDS / Aurora | yes (managed) |
| kafka | MSK | yes |
| redis | ElastiCache | yes |
| rabbitmq | Amazon MQ | yes |
| mongodb | DocumentDB / Atlas | yes |
| temporal | Temporal Cloud | external SaaS |
| minio | S3 (+ CloudFront) | serverless |
| prometheus/grafana/jaeger/loki | Amazon Managed Prometheus+Grafana / Datadog | managed |
| frontend | S3 + CloudFront | serverless |
| ingress | ALB | managed |

**Where managed-service variables live (the key point — yes, we still store them):** AWS runs the service but we must store its endpoint + credentials somewhere the pods read. Flow:

```
AWS Secrets Manager (source of truth, rotated by AWS)
   → External Secrets Operator syncs hourly
   → k8s Secret smartcourse-secrets (auto-created in cluster)
   → pods envFrom secretRef
```

Non-secret coordinates (hostnames, bucket) → `configmap.yaml`. Secret parts (full DSNs with creds, keys) → AWS Secrets Manager, pulled in by the ESO `ExternalSecret` (`external-secret.example.yaml`). Auth to AWS uses IRSA — no static keys anywhere. Nothing sensitive is ever committed or hardcoded.

**Cost reality:** the managed-services floor alone is ~$1,100/mo (EKS $73 + nodes ~$200 + RDS ~$140 + MSK ~$250 + ElastiCache/MQ/DocumentDB ~$300 + Temporal/S3/CloudFront/ALB ~$150). This is why the k8s manifests are the *artifact proving the approach*, while docker-compose is what we actually run for the assignment.

### Q: What is Ingress, what do the 14 k8s files do, and why exactly is the k8s-vs-managed split drawn at "state"?

**A:**

**Ingress vs Service** — two different problems:
- A **Service** (Layer 4) gives a *stable internal address* and load-balances across pods (pods are ephemeral, IPs change, so you can never point at a pod directly). `ClusterIP` = internal only.
- An **Ingress** (Layer 7 / HTTP) is the *public front door* — TLS termination, hostname + path routing. It's the only internet-facing piece. On AWS it's backed by an ALB.
- Request path: `browser → Route53 → ALB (Ingress, TLS) → Service (LB) → one api pod`. Node analogy: Ingress ≈ nginx reverse-proxy + TLS; Service ≈ the internal LB it forwards to. Only `api` has a Service+Ingress; the 5 workers reach *out* (to Kafka/DB) so nothing connects *to* them.

**The 14 files by k8s object kind:**
- Identity/config: `namespace` (isolation boundary), `configmap` (non-secret env), `secret.example` (shape template), `external-secret.example` (real prod: ESO ← AWS Secrets Manager).
- One-shot: `migrate-job` — a Job runs `alembic upgrade head` to completion then exits (≠ Deployment).
- Workloads (our code): 6 Deployments (api, worker, relay, welcome-email-consumer, events-archiver, celery-worker) — a Deployment keeps N pods alive, heals + rolls them.
- Networking: `api-service`, `ingress`.
- Scaling: `hpa` (6 HorizontalPodAutoscalers).

**Why the split is at STATE:**
- Stateless (→ k8s): our api/workers hold no data, any replica == any other, kill one → just restart, scale = add identical copies ("cattle").
- Stateful (→ managed): postgres/kafka/redis/etc. ARE the data, each replica is unique, kill one → data loss risk, scale = resharding ("pets").
- Stateful is hard in k8s because of: (1) storage identity — pod disks vanish on restart, need StatefulSet+PVC+EBS; (2) cluster quorum — brokers/primaries must re-form leadership without split-brain when pods reschedule; (3) backups/PITR/failover — RDS does it automatically, in k8s you build+test it yourself; (4) upgrades — one click vs a project.
- You *can* run stateful in k8s via Operators (CloudNativePG, Strimzi) but it needs a platform team + on-call. Rule: don't run stateful in k8s unless operating it is someone's job. We don't, so: stateless → k8s, data → managed.
- Mental model: **k8s is a scheduler for interchangeable disposable compute — great at healing many identical stateless copies, fighting its nature when babysitting unique precious nodes. Managed services absorb that hard part.** k8s schedules our cattle; AWS tends the pets.

### Q: Is Ingress an AWS service? What AWS compute options exist for our project (we considered EC2)?

**A:** **Ingress is NOT an AWS service — it's a Kubernetes spec.** By itself it does nothing; it needs an Ingress Controller, and on AWS that controller (AWS Load Balancer Controller) provisions an actual **ALB**. So: Ingress = portable k8s abstraction; ALB = the AWS thing implementing it. Same `ingress.yaml` works on any cloud — only the controller underneath changes. (Raw TCP → NLB instead.)

**Compute spectrum for SmartCourse (simplest → most scalable):**

1. **Single EC2 + docker-compose** — one EC2, install Docker, `git pull && docker-compose up -d`. Our exact local setup on a cloud box. Cheapest (~$120/mo for one t3.xlarge), zero new concepts. Cons: single point of failure, no autoscaling, you patch the OS + own backups, data on instance disk. Legitimate for demos/MVPs/this assignment.

2. **ECS / Fargate** — AWS's container orchestrator, no k8s. Fargate = serverless (no EC2 to manage). Container orchestration + autoscaling without learning k8s; AWS-locked (not portable). Sweet spot for many teams.

3. **EKS (managed k8s)** — full k8s, what `deploy/k8s/` targets. Most powerful + complex + expensive (~$1,100/mo floor). Overkill for a learning project.

**Full AWS service map:** compute → EC2/ECS-Fargate/EKS; LB → ALB/NLB; DNS → Route53; Postgres+pgvector → RDS/Aurora; Kafka → MSK; Redis → ElastiCache; RabbitMQ → Amazon MQ; Mongo → DocumentDB/Atlas; Temporal → Temporal Cloud; object storage → S3+CloudFront; frontend → S3+CloudFront; secrets → Secrets Manager; images → ECR; observability → Managed Prometheus+Grafana / CloudWatch / X-Ray; CI/CD → CodePipeline / GitHub Actions; GPU for Whisper → EC2 g4dn/g5 or SageMaker.

**Recommendation:** EC2+docker-compose is the floor (start here — our setup on a cloud box), EKS is the ceiling. The k8s manifests are the "here's how at scale" artifact proving the production end-state, without needing to actually run a $1,100/mo EKS stack. Pick by scale.

### Q: Why do we need RAG if semantic search already works over video/text/pdf? How is it better?

**A:** Semantic search IS the "R" (Retrieval) in RAG — we're already most of the way there. The question is whether the "G" (Generation) earns its place. They answer different questions:
- Search → "WHERE is this covered?" — returns raw chunks, student interprets them.
- RAG → "WHAT's the answer?" — feeds the same retrieved chunks to an LLM, returns a synthesized natural-language answer grounded in them.

Same retrieval step; RAG adds an LLM on top.

Concrete (our Sintel data), query "what is the dangerous quest?":
- Search returns the raw chunk ("...the dangerous quest for unknown unto...") and you figure it out.
- RAG returns "The dangerous quest refers to the protagonist's search for someone they've lost..." — a direct conversational answer.

4 things RAG does that search can't:
1. Synthesis — combine 5 chunks into one coherent answer (search returns 5 separate passages).
2. Natural-language answer to the actual question (vs read+interpret raw text).
3. Reasoning across chunks — "summarize what this course teaches about X" or "compare flow A vs flow B": no single chunk IS the answer; the LLM generates new text grounded in many. Search physically cannot — it only returns closest existing text.
4. Conversation — follow-ups.

Why RAG ≠ just ChatGPT: raw ChatGPT knows the world but not YOUR course → hallucinates. Raw search is grounded but dumps text. RAG = an LLM "on a leash" to your content: the prompt forces "answer ONLY from these retrieved chunks; if not there, say you don't know." Combines the LLM's language ability with your data's factual grounding — that's the whole reason the pattern exists.

Honest tradeoff (don't oversell): RAG adds latency (1–5s LLM call vs ~50ms search), cost (an LLM call per query), and a mis-synthesis failure surface. So for navigation ("find the lecture about recursion") plain search is better — instant, free, exact. Real platforms ship BOTH: search for finding pages, RAG for answering questions. We already built the valuable half (retrieval); RAG is a thin layer — wrap retrieved chunks in a prompt, call an LLM, stream the answer (Week 5's deliverable).

### Q: Is RAG free?

**A:** Retrieval half = already free; generation half = free only with a local LLM. RAG has two halves:
- Retrieval (built): embeddings (sentence-transformers) + pgvector search — all local, $0.
- Generation (Week 5): the LLM that writes the answer — this is the only new cost.

**Free path — Ollama (local), matches our whisper/embedding choices:** run a small open model (llama3.2:3b ~2GB, phi3.5, qwen2.5:3b — CPU-runnable with 8GB+ RAM; mistral:7b heavier). Free in dollars, but pays in resources: ~3–4GB RAM, CPU pegged while generating, ~5–30s/answer on CPU (streaming hides it), one-time ~2GB download, 3B-quality (good not GPT-4-good). Same trade as Whisper: $0 but slower.

**Paid path — cloud API (comparison):** OpenAI gpt-4o-mini ~$0.15/1M input + $0.60/1M output; a typical RAG query (~2K in, 300 out) = fractions of a cent. Cheap absolutely, but needs a key + sends course content to a third party.

**Recommendation:** Ollama + llama3.2:3b — keeps the whole platform free + self-contained (clone → working RAG, no key, no bill), adds one `ollama` container. Code is identical to the API path, so swap Ollama → OpenAI later with a one-line client change. The one place "free" is noticeably slower: 3B-on-CPU ~10–20s vs cloud ~1s (a GPU makes local both free AND fast). Start free, swap if needed.

### Q: Week 5 — how was the RAG Q&A assistant built and verified?

**A:** RAG = the Week 4 retrieval + an LLM on top. Free/local stack (Ollama), swappable to a cloud API via one module.

Pieces:
- `services/llm_service.py` — streams chat tokens from Ollama (`/api/chat`, NDJSON); the ONLY LLM-vendor code.
- `services/rag_service.py` — embed question → `search_repo.search_chunks` (reuses Week 4) scoped to the course → drop chunks below `rag_min_similarity` (0.15) → grounded prompt → stream. If no chunk clears the floor, returns a canned "not covered" message WITHOUT calling the LLM (no hallucination, saves the round trip).
- `routers/assistant.py` — `POST /api/v1/assistant/ask`, SSE streaming, JSON-encoded tokens (handles markdown newlines), `[DONE]` sentinel.
- Frontend: `api/assistant.ts` (fetch + SSE reader, JWT attached manually), `AssistantPanel.tsx` (live streaming chat with markdown), wired into the course page beside search.
- Infra: `ollama` + `ollama-pull` (one-shot model pull) in compose, `ollama_data` volume, `OLLAMA_HOST`/`OLLAMA_MODEL` config, `llama3.2:3b`.

Verified end-to-end against the Sintel course (Whisper transcript of the uploaded video):
- Q "what is the dangerous quest?" → grounded answer quoting the transcribed dialogue ("dangerous quest for unknown unto…") — full chain video→Whisper→chunk→embed→retrieve→LLM.
- Q "capital of France?" → "I don't have information about that in this course" — the LLM refused outside knowledge despite obviously knowing it. Grounding leash works.

Gotchas hit: (1) the api container needed recreating to pick up the `OLLAMA_HOST` env added during this work (40h-old container predated the compose edit). (2) First system prompt was too refusal-happy — the 3B model bailed on a short fragmentary transcript; softened it to "treat context as authoritative, answer even if brief; only refuse if nothing related" → grounded answers started working while the off-topic guardrail still held. (3) Ollama image (7.29GB) repeatedly hit `unexpected EOF` on a flaky connection; eventually pulled on retry.

Honest note: llama3.2:3b on CPU is slow (~seconds) and modest quality; streaming hides the latency, and swapping to a cloud API (OpenAI/Anthropic) is a one-file change in `llm_service.py`.

### Q: Search returned the Sintel chunk for "capital of france" at 0% match — bug? Plus: SSE, JSON-encoded tokens, Ollama image vs model, guardrails, seeing the whole flow.

**A:**

**The 0%-match "bug":** that was the SEMANTIC SEARCH panel (not RAG). ANN always returns the *nearest* chunks even when none are relevant, so an off-topic query surfaced the only chunk at ~0%. Fixed: `search_service` now drops hits below `rag_min_similarity` (0.15); irrelevant queries return empty → UI shows "this course doesn't seem to cover it." Verified: "capital of france" → 0 results; "the quest to find someone" → 54% match.

**SSE (Server-Sent Events):** server pushes the response incrementally over one HTTP connection instead of all-at-once. The LLM generates word-by-word; SSE shows words as they're produced (ChatGPT-style) instead of a 10–20s spinner. Format: `data: <chunk>\n\n` lines, ended by `data: [DONE]`.

**JSON-encoded tokens:** SSE uses newlines as frame separators, but LLM output contains newlines/markdown. So each token is `json.dumps()`-wrapped (`data: "line one\nline two"`) so a token's newline can't break the frame; the frontend `JSON.parse`s it back.

**Ollama image vs llama model:** the image (7.29GB) is the *software/server that runs LLMs* (like VLC); the model llama3.2:3b (2GB) is the *trained weights* (like a movie file). One image runs many models. Pulled separately: `docker pull ollama/ollama` (engine) then `ollama pull llama3.2:3b` (content into its volume).

**Guardrails (rag_service):** (1) course scoping — retrieval only searches this course's chunks; (2) similarity floor — sub-0.15 chunks dropped, and if none clear it we return a canned "not covered" WITHOUT calling the LLM (can't hallucinate if it never runs); (3) grounded prompt — "answer ONLY from context, no outside knowledge." That's why "capital of France?" → "I don't have that information" despite the model knowing Paris.

**Seeing the full flow (video→storage→publish→chunk→embed→RAG):** each stage lives in a different tool — MinIO :9001 (uploaded object), Temporal :8080 (publish activities), Loki/Grafana :3000 (worker whisper/chunk logs), Kafka UI :8081 (events), Postgres (lesson_chunks vectors), Prometheus/Grafana (rates/latency), Jaeger :16686 (per-request traces). Honest limitation: tracing is stitched WITHIN the API (one request → its DB spans, shared trace_id) but the async pipeline (publish→Kafka→consumer→worker) produces separate per-service traces — correlate those by `course_id` in Loki. One-trace-across-async needs traceparent propagation through outbox/Kafka headers (documented Week 3 enhancement). To watch live: tail `docker-compose logs -f worker relay events-archiver api`, publish a fresh course, and watch Temporal + Kafka UI + Grafana/Loki + MinIO update in real time.

### Q: Add global semantic search across the user's enrolled courses (not just one course).

**A:** Added `POST /api/v1/search/my` — searches across only the courses the caller may access, derived from their role (the access-control boundary):
- student → courses they're enrolled in (excludes dropped)
- instructor → courses they own
- admin → all courses (no scope filter)

Implementation:
- `search_repo.search_chunks` gained a `course_ids: list | None` param (IN-filter); empty list short-circuits to no results (avoids degenerate `IN ()`).
- `search_repo.enrolled_course_ids` / `owned_course_ids` compute the access set.
- `search_service.global_search` picks the set by role, embeds the query, retrieves, applies the same `rag_min_similarity` floor.
- Endpoint `/search/my` (any authenticated user); the existing `/search/semantic` (single-course) is unchanged.
- Frontend: `components/GlobalSearch.tsx` on the Catalog page — each hit links to its course (`course_title · lesson_title`).

Why not earlier / why scoped: a naive "search all lesson_chunks" leaks draft/other-instructors'/non-enrolled content. The fix is filtering retrieval to the user's accessible course set — that's the security boundary. (The RAG assistant stays single-course by design — "ask THIS course" — for relevance/grounding; global search is a different, additive UX.)

Verified: student NOT enrolled → 0 results (no leakage); same student after enrolling in the course → finds the chunk (54% match), scoped to their enrollment.

## Observability use cases (real failure → diagnosis → fix)

### UC1 — "Students aren't getting welcome emails"

**Symptom:** student enrolls, gets HTTP 201, sees the course in My Learning — but no welcome email arrives. (No user-visible error; the request succeeded.)

**Reproduce:** `docker-compose stop celery-worker`, then enroll a student.

**Debug method — walk the pipeline, find the FIRST broken hop:**
1. **Loki** — `{container="smart-course-welcome-email-consumer-1"} |= "enqueued"` → the consumer DID enqueue the task. So the break is *downstream* of the consumer.
2. **RabbitMQ management API** (the smoking gun) — `curl -u guest:guest http://localhost:15672/api/queues/%2F/celery` → `1 message waiting, 0 consumers attached`. Messages piling up with **zero consumers** = the worker that drains this queue is gone. **Root cause.**
   (Or RabbitMQ UI http://localhost:15672 → Queues → `celery` → see depth climbing, consumers = 0.)
3. **celery-worker logs** — zero `welcome-email` executions in the window → confirms it's not running.
4. **`docker-compose ps celery-worker`** → `Exited` → confirmed.

**Fix:** `docker-compose start celery-worker`. The queue drains to 0, consumers = 1, and the previously-stuck email fires — proving the task was durably queued in RabbitMQ the whole time (**no data loss**; the work just waited).

**Lesson:** a 201 to the user doesn't mean the whole async pipeline succeeded. The decisive signal here is **queue depth + consumer count** (RabbitMQ), not the API logs. "Messages waiting, 0 consumers" instantly localizes a dead worker. The durability of the broker means recovery = just restart the worker; queued work replays.

### Q: Where is the ALERT? How do we get notified that something is down (not just investigate after noticing)?

**A:** Originally: nowhere. What we'd built (Grafana/Loki/Jaeger/Prometheus) was **observability for investigation** — tools you open *after* you suspect a problem. UC1/UC2 had no alert; we only found issues by looking. Two gaps: (1) no alerting layer; (2) Prometheus only scraped the API — the workers exposed no `/metrics`, so there was no `up{job="celery-worker"}` signal to even alert on.

**Built real alerting (Grafana-managed, panel-only):**
1. **Worker metrics** — `app/observability/metrics_server.py` runs `prometheus_client.start_http_server(9100)` in each long-running worker (relay, welcome-email-consumer, events-archiver, temporal worker via `_run()`; celery-worker via the `worker_init` signal). Now each worker serves `/metrics`.
2. **Scrape targets** — `prometheus.yml` gained jobs for relay / welcome-email-consumer / events-archiver / temporal-worker (`worker:9100`) / celery-worker. Verified all 7 targets `up`.
3. **Alert rules** — `observability/grafana/provisioning/alerting/alerts.yaml`, Grafana-managed:
   - `SmartCourse service is down` — fires when `up{job=~...} < 1` for 1m (any worker dead).
   - `SmartCourse API 5xx error rate elevated` — `rate(http_requests_total{status=~"5.."}[5m]) > 0.2` for 2m.
   Datasource needs a stable uid (`uid: prometheus`) for the rule to reference it.
4. **No contact point** (panel-only): alerts show in Grafana → Alerting. Add a Slack/email contact point later to get pushed notifications.

**Demonstrated the full lifecycle:** stopped celery-worker → `up=0` within ~10s → alert `pending` for the 1-minute `for:` grace → `firing` at ~72s. Restarted it → `up=1` → alert back to `inactive` within ~36s. This turns UC1/UC2 from "I went and looked" into "Grafana flags it on its own."

**Key concepts:** observability (investigate) ≠ alerting (detect). An alert = a rule evaluated on a timer (`up==0 for 1m`) → fires → routed to a contact point. The `for:` duration is the grace period that avoids flapping on a blip. `up` is Prometheus's built-in per-target scrape-success metric (1=reachable, 0=not) — the simplest, most reliable "is it alive" signal, which is why exposing `/metrics` on every worker was the prerequisite.

### Q: Add Ollama (and everything else without native metrics) to alerting.

**A:** Ollama and the infra (Postgres/Redis/RabbitMQ/Kafka/Mongo/Temporal/MinIO) don't expose Prometheus metrics, so `up`-based alerts couldn't see them — UC4 (Ollama down) was invisible to alerting. Fixed with **blackbox-exporter**, the standard probe-from-outside approach.

- `observability/blackbox.yml` — two modules: `http_2xx` (HTTP GET, success on 2xx) and `tcp_connect` (port accepts a connection).
- `blackbox-exporter` service in compose (prom/blackbox-exporter), config mounted.
- `prometheus.yml` — two probe jobs using the standard relabel pattern (Prometheus calls `blackbox-exporter:9115/probe?target=<x>`; the exporter connects to `<x>` and returns `probe_success`; relabel rewrites `instance` = the real target):
  - `blackbox-http` → `http://ollama:11434/`
  - `blackbox-tcp` → postgres:5432, redis:6379, rabbitmq:5672, kafka:9092, mongo:27017, temporal:7233, minio:9000
- Grafana alert `SmartCourse dependency is down` — `probe_success == 0 for 1m`, labelled by `instance` so you see which dependency.

Verified: all 8 probes `up`; stopped Ollama → `probe_success{ollama}=0` → alert `pending` (60s grace) → `firing` (~108s) → restarted → `inactive`. UC4 is now alertable.

**Full alerting coverage now:** our own workers via `up` (Prometheus scrapes their `/metrics` on :9100); Ollama + all infra via `probe_success` (blackbox). Three rules: service-down (workers), dependency-down (Ollama+infra), API-5xx-rate. Concept: `up` = "did Prometheus scrape my /metrics?" (for things that expose metrics); `probe_success` = "could blackbox reach this endpoint?" (for things that don't). Together they cover every component.

### Q: What is a probe / blackbox? How is data gathered for metrics vs logs vs traces?

**A:** **Black-box monitoring** = testing a system from the OUTSIDE, like a user, with no knowledge of internals — you knock and see if it answers. Contrast **white-box** = the app exposes its own internal metrics.

| | White-box | Black-box |
|---|---|---|
| How | app exposes /metrics | probe from outside |
| Knows | internal state (counts, queue depth) | only "is it reachable?" |
| Ours | api + workers /metrics → scraped | blackbox-exporter → Ollama/infra |
| Metric | http_requests_total, up | probe_success, probe_duration_seconds |

A **probe** = one outside test (HTTP GET → 2xx? / TCP connect → port open?) reporting `probe_success` 1/0. Used for things that can't report their own metrics (Ollama, databases) — the only knowable fact is "could I reach it?".

**Collection model differs per pillar — the insight is WHO initiates the data movement:**
- **Metrics = PULL.** Prometheus reaches out and scrapes `/metrics` every 10s (white-box) + scrapes blackbox-exporter for probe results (black-box). Because Prometheus initiates, it instantly knows if a target is unreachable (`up=0`). → stored in Prometheus TSDB → Grafana dashboards + alert rules.
- **Logs = SHIP.** Each service writes JSON to stdout → Docker json-file → Promtail tails the files and pushes to Loki → Grafana (LogQL). The app just prints; it doesn't know Loki exists.
- **Traces = PUSH.** The app's OpenTelemetry SDK actively sends spans (OTLP gRPC) to Jaeger as requests happen → Jaeger UI.

Everything funnels into Grafana as the single pane; alert rules sit on the metrics to detect proactively. One-liner: metrics = Prometheus comes to you (pull); logs = an agent ships your stdout (Promtail→Loki); traces = you push spans (→Jaeger).

### UC6 — Events log / analytics stops updating (events-archiver down)
**Pillar:** Loki logs + service-down alert + Kafka durability.
**Bug induced:** `docker-compose stop events-archiver` (the Kafka→Mongo consumer). Mongo baseline 378 events.
**Reproduce:** perform any event-emitting action (enroll / complete lesson).
**Symptoms / observe:**
- Mongo `db.events.countDocuments()` stays at 378 — the event log/analytics stops growing.
- Kafka UI (:8081) → topic `events.user.enrolled` → the new message IS there → event not lost, just not consumed.
- Grafana → Alerting: "SmartCourse service is down" fires (~1m), labelled events-archiver.
- Grafana → Loki: `{container="smart-course-events-archiver-1"}` has no recent lines.
**Fix:** `docker-compose start events-archiver` → rejoins its Kafka **consumer group at the last committed offset**, processes every missed event, Mongo count jumps past 378. **Zero loss** — Kafka held the backlog; consumer resumed exactly where it stopped.
**Lesson:** a downstream consumer dying causes a *store to stop growing*, not data loss — Kafka is the durable buffer. Detection = service-down alert + stale Loki stream.

### UC5 — Enroll slow under load: metric → trace drill-down (Jaeger)
**Pillar:** Prometheus p95 (detection) + Jaeger tracing (root cause).
**Scenario (not a bug — correct behavior under a stampede):** 40 students enroll in one capacity-limited course simultaneously. Enroll does `SELECT course FOR UPDATE` + count + INSERT, so the row lock serializes concurrent enrollers on the same course.
**Reproduce:** fire 40 concurrent enrolls (5 rounds). p95/max climb vs a single request.
**Detect (Prometheus/Grafana Explore):**
`histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{handler=~".*enroll.*"}[1m])) by (le))` → spikes during the burst.
**Root-cause (Jaeger :16686, service smartcourse-api, the enroll op, Min Duration 50ms):** a ~123ms trace decomposed as: `connect` 23ms (**pool contention** — 40 concurrent > pool_size, requests queue for a connection) + `SELECT … FOR UPDATE` 76ms (**row-lock wait** — blocked on another txn holding the course row) + count 0.7ms + `INSERT` 0.5ms. ~80% of latency is *waiting*, not *working*.
**The red ⊘ on the INSERT span:** on re-run rounds the student is already enrolled, so INSERT hits `UNIQUE(student_id, course_id)` → IntegrityError → service catches it → **409**. OTel marks the SQL span errored (a *statement* error) but NO 5xx happens (not a *request* error) — so error-rate alerts correctly stay quiet. This is the idempotency-via-DB-constraint guard working, visible one layer deeper than metrics.
**Lesson:** the histogram gives the number (p95=123ms); the trace names the culprit (76ms lock + 23ms pool wait) → fixes: shrink the locked txn / use atomic `UPDATE … WHERE enrolled < capacity`; raise pool_size. Metrics detect, traces diagnose.

---

## Session — 2026-06-08 (LLM tokens, RAG flow, tok/s, local vs cloud)

### Q: How are LLM tokens produced in SmartCourse? What is the whole `/ask` flow, and what does tok/s depend on?

**A:** A **token** is not something SmartCourse invents — it is a sub-word piece from the **LLM's tokenizer** (roughly ¾ of a word in English). The model reads tokens in (prompt) and writes tokens out (completion). Our app **streams** those output pieces to the browser; Ollama reports the counts on the final `done` JSON line.

**End-to-end flow for `POST /api/v1/assistant/ask`:**

```
Browser
  │  SSE stream (one JSON-encoded text chunk per frame)
  ▼
assistant router (assistant.py)
  │  async for token in rag_service.answer_stream(...)
  ▼
rag_service.answer_stream
  ├─ 1. retrieve()
  │     ├─ embedding_service.embed([question])   ← CPU, ~50ms warm / ~8s cold
  │     └─ search_repo.search_chunks (pgvector) ← ~10ms
  ├─ 2. if no hits above similarity floor → canned reply, NO LLM call
  ├─ 3. build_prompt() — trim chunks to RAG_MAX_CHUNK_TOKENS, assemble context
  └─ 4. llm_service.stream_chat(system, user_prompt)
        ├─ POST http://ollama:11434/api/chat  (stream=true)
        ├─ Ollama phase A: load model (first request after restart)
        ├─ Ollama phase B: prompt_eval — read ALL input tokens (prefill)
        ├─ Ollama phase C: eval — generate output tokens one-by-one
        └─ each streamed line: {"message":{"content":"..."}, "done":false}
           final line: {"done":true, "prompt_eval_count":N, "eval_count":M, ...}
```

**Two token counts matter:**

| Kind | Ollama field | What it is | What it depends on |
|---|---|---|---|
| **Input / prompt tokens** | `prompt_eval_count` | Everything sent to the model: system prompt + RAG context + question | `RAG_TOP_K`, `RAG_MAX_CHUNK_TOKENS`, chunk text length, system prompt size. **Prefill time scales ~linearly with this.** |
| **Output / completion tokens** | `eval_count` | Tokens the model **generated** as the answer | Question complexity, how much the model decides to say, `temperature`. Shorter grounded answers → fewer output tokens. |

**Where output tokens are actually created:** inside the **Ollama container** (or a cloud API's GPUs in production). SmartCourse only forwards them. `llm_service.stream_chat` yields `obj["message"]["content"]` per line; the router wraps each chunk in SSE.

**tok/s (tokens per second)** = `eval_count / eval_duration` — output tokens divided by **generation time only** (phase C). It does **not** include prefill (phase B) or TTFT. Recorded in `llm_service._record_completion` and exposed as `llm.ollama.tokens_per_second` on the Jaeger span and on the LLM/RAG Grafana dashboard.

**Why we previously saw ~2 tok/s:** with `llama3.2:3b` running on **CPU inside Docker**, matrix math for autoregressive decoding is slow — ~2–3 output tokens per second is normal. Prefill on a ~2,000-token prompt took **~120–170 s** before any token appeared; generation added another **~30 s** for ~70 tokens. That is a hardware/model-size limit, not a bug in our code.

**After optimization (1b model + smaller prompt):** warm runs showed **~13 tok/s** generation and **~9 s TTFT** — same flow, less work per phase.

**Prometheus metrics tied to tokens:**
- `smartcourse_llm_prompt_tokens` — histogram of input size
- `smartcourse_llm_tokens_generated_total` — counter of output tokens
- `smartcourse_llm_time_to_first_token_seconds` — wall-clock until first streamed chunk (prefill + network)
- `smartcourse_llm_prompt_eval_seconds` / `smartcourse_llm_eval_seconds` — Ollama's own phase timings

**Grafana:** SmartCourse — LLM / RAG dashboard (`/d/smartcourse-llm-rag`) charts all of the above without writing PromQL by hand.

### Q: If we swap Ollama for OpenAI or Anthropic, why do replies get fast? Does the heavy CPU run there?

**A:** Yes. With Ollama locally, **your machine's CPU** runs the full transformer inference (billions of floating-point ops per token). With OpenAI/Anthropic/Groq, **their GPUs** run it; our API only sends an HTTPS request and streams the response back.

| | Local Ollama (dev) | Cloud API (prod) |
|---|---|---|
| **Where inference runs** | Ollama container on your CPU (no GPU in Docker on Mac) | Provider data center on **GPUs** (often thousands of cores / tensor cores) |
| **What SmartCourse does** | Build RAG prompt → `POST /api/chat` → stream JSON lines | Same orchestration; only `llm_service.py` changes (different HTTP client + auth) |
| **Typical TTFT** | 10–120+ s on CPU for large prompts | Often **< 1–3 s** |
| **Typical tok/s** | 2–15 on CPU (model-size dependent) | **50–500+** on GPU-backed APIs |
| **Cost** | Free, slow | Pay per input + output token |

The RAG pipeline (embed question → pgvector search → build prompt) stays on **our API** in both cases — that part is milliseconds. The speedup from cloud APIs is almost entirely in **phases B and C** (prefill + generation), which move off your laptop onto specialized hardware.

**Production swap is one file:** `backend/app/services/llm_service.py` — swap the Ollama `httpx` stream for the vendor's chat-completions streaming API. `rag_service`, the router, metrics, and Jaeger spans stay the same; you'd map their usage fields to the same `gen_ai.usage.*` attributes.

**Rule of thumb:** input tokens control **how long "thinking…" lasts** (shrink RAG context); output tokens control **how long streaming lasts** (ask for concise answers); **hardware** controls **tok/s** (local CPU slow, cloud GPU fast).

### Q: Are we running a local model? Is our local model actually producing the tokens? (LLM perspective)

**A:** **Yes on both.** SmartCourse does not generate text — **Ollama running `llama3.2:1b` on your machine's CPU** is the only component that produces answer tokens. The API retrieves context, builds a prompt, calls Ollama, and pipes streamed chunks to the browser.

**What runs where (dev stack):**

```
Your laptop / Docker host
├── smart-course-api-1        ← SmartCourse (Python/FastAPI)
│     RAG: embed question, pgvector search, build prompt
│     llm_service: POST /api/chat, stream response to browser
│
└── smart-course-ollama-1     ← Ollama server
      loads llama3.2:1b weights (~1.3 GB, ollama_data volume)
      runs the neural network on YOUR CPU
      ★ produces tokens here ★
```

- **Model:** `llama3.2:1b` (Meta Llama 3.2, ~1B parameters) — configured in `config.py` / `OLLAMA_MODEL` / docker-compose.
- **Call site:** `llm_service.stream_chat` → `POST http://ollama:11434/api/chat` with `"stream": true`.
- **Not the chat LLM:** `sentence-transformers/all-MiniLM-L6-v2` in `embedding_service` only embeds the question for search — it does not write the answer.

**From the LLM's perspective — what happens inside Ollama:**

1. **Tokenize** — system prompt + RAG context + question → integer token IDs (e.g. ~773 input tokens after our RAG tuning). The model never sees raw English.

2. **Prefill (prompt_eval)** — one forward pass over all input tokens; builds internal state ("I've read all this context"). **No output tokens yet** — this is the "thinking…" gap. Slow on CPU; scales with prompt length.

3. **Generate (eval)** — autoregressive loop: predict next token → append → predict next → … until stop:
   ```
   [prompt]           → "This"
   [prompt + "This"]  → " course"
   [prompt + ...]     → " covers"
   ...
   ```
   Each step is another forward pass through Llama's weights on your CPU. **Every word in the streamed UI is a token (or sub-token) Llama just predicted locally.**

4. **Done frame** — Ollama sends `{"done": true, "prompt_eval_count": N, "eval_count": M, ...}`. SmartCourse records these in metrics/Jaeger; it does not compute them itself.

**Who does what:**

| Layer | Produces answer tokens? |
|---|---|
| RAG (`rag_service`) — retrieve + build prompt | No — text assembly only |
| Embedding model — vector search | No — not the chat LLM |
| **Ollama / `llama3.2:1b`** | **Yes — the only token producer** |
| API (`llm_service`, `assistant`) — HTTP + SSE | No — pipe only |

**Analogy:** SmartCourse is the librarian (finds pages, writes the question). Ollama/Llama is the author (writes the answer one word at a time). The librarian delivers; they don't author.

**Verify it's truly local:**
- `docker exec smart-course-ollama-1 ollama list` → shows `llama3.2:1b` on disk.
- `docker stop smart-course-ollama-1` → assistant fails (Grafana Ollama probe goes red).
- Jaeger trace → long span is `POST http://ollama:11434/api/chat`, not an external API.
- Inference needs no internet once the model is pulled — weights live in the `ollama_data` volume.

**Local vs cloud — same LLM mechanics, different hardware:**

| | Now (local) | Prod (OpenAI/Anthropic) |
|---|---|---|
| Who produces tokens | Llama in Ollama on your CPU | Their model on their GPUs |
| SmartCourse's job | Build prompt, stream response | Identical — only `llm_service.py` changes |
| Speed limiter | Your CPU + model size | Their GPU infra |

**One-liner:** `llama3.2:1b` inside Ollama reads the RAG prompt and generates every answer token on your machine; SmartCourse retrieves context, sends the prompt, and forwards the stream.

### Q: How does instructor summary/quiz generation work?

Same RAG pipeline as student Q&A, different prompts and auth:

1. **Auth** — `POST /assistant/generate` requires instructor (or admin) and course ownership. Ownership is validated *before* the SSE stream starts so 403/404 return as normal HTTP errors.
2. **Context** — If `lesson_id` is set, all indexed chunks for that lesson are loaded. If omitted, semantic retrieval over the whole course (same embedding + pgvector path as search).
3. **Generation** — `kind: "summary"` uses a bullet-point instructor prompt (`temperature=0.2`); `kind: "quiz"` uses a strict markdown template with numbered questions, A–D options, correct answer, and explanation (`temperature=0.1`).
4. **Prerequisite** — `lesson_chunks` must exist from a prior publish (Temporal `process_lessons_activity`). Without indexed content the stream returns a single message explaining that.
5. **UI** — Course detail page shows **Instructor tools** (`GenerationPanel`) for course owners on published courses; streams tokens like the student assistant panel.

Quiz markdown template (one block per question):

```
### Question N
**Question:** ...
- A) ...
- B) ...
- C) ...
- D) ...
**Correct answer:** A|B|C|D
**Explanation:** ... (citing lesson title)
```

---

## Session — 2026-06-08 (Tier 2 + dev admin)

### Q: What are the SmartCourse dev admin login credentials?

**A:** After `docker compose up` (migrate runs seed automatically):

| Role | Email | Password |
|---|---|---|
| **Admin** | `admin@smartcourse.local` | `SmartCourseAdmin1!` |
| **Instructor (demo)** | `instructor@smartcourse.local` | `SmartCourseInstruct1!` |

Login: `POST /api/v1/auth/login` with `{ "username": "<email>", "password": "<password>" }` (OAuth2 form field names). Override via `.env`: `DEV_ADMIN_EMAIL`, `DEV_ADMIN_PASSWORD`, etc. Set `SEED_DEV_USERS=false` to skip.

**Note:** Grafana is separate — default `admin` / `admin` at http://localhost:3000.

### Q: What did Tier 2 add?

**A:**

1. **Mailhog + real welcome email** — `mailhog` service in compose; Celery `send_welcome_email` sends SMTP to Mailhog (UI http://localhost:8025).
2. **Certificates** — Issued idempotently when enrollment auto-completes; `GET /api/v1/certificates/me` (student).
3. **traceparent propagation** — Captured on outbox emit, forwarded in Kafka headers, restored in welcome-email consumer, events-archiver, and Celery tasks.
4. **Re-index** — `POST /api/v1/courses/{id}/reindex` (202) enqueues Celery `tasks.reindex_course`; shared `content_indexing_service` with publish workflow.

---

## Session — 2026-06-09 (Deferred features: prerequisites, cache, recommendations, schema registry)

### Q: Why do we need a Kafka Schema Registry?

**A:** It's a versioned store of your event schemas (Avro / Protobuf / JSON Schema) sitting next to Kafka. The producer's serializer registers a schema and stamps every message with a schema-ID header; consumers read that ID and fetch the matching schema to decode. The point that matters is it **enforces a compatibility policy on every schema change**.

**Problem it solves in SmartCourse:** our three events (`user.enrolled`, `lesson.completed`, `course.published`) are hand-rolled JSON dicts decoded by three independent consumers (welcome-email, events-archiver, analytics). That shape is an *implicit contract with zero enforcement* — rename `student_id → user_id` in the producer and consumers break at runtime, asynchronously, on a fraction of messages. Schema Registry makes the contract explicit and **rejects an incompatible change at the producer**, before a bad message reaches the topic. Secondary wins: smaller payloads (binary + schema ID) and a single source of truth for each event shape.

**In Node terms:** like sharing a versioned protobuf / `@types` package between microservices, except the registry enforces compatibility at the wire boundary at runtime instead of trusting every service to rebuild — a CI gate that blocks a breaking change to a published OpenAPI/GraphQL schema, but for Kafka messages.

**Honest take for this system:** lowest-ROI of the deferred features. One codebase, one team, we own every producer + consumer, three event types — the failure it prevents (independent teams evolving a shared topic out of sync) doesn't exist here yet. You'd get ~80% of the safety with a Pydantic model validating the envelope on the producer + a `schema_version` field. Worth doing because (1) it's in the prescribed stack and (2) it teaches the core lesson: **events are contracts; contracts need versioning + a compatibility policy.** Do it with `BACKWARD` compatibility and a test that proves a breaking change is rejected.

### Q: How do you stop course prerequisites from forming a cycle?

**A:** Prerequisites are a directed graph (edge "A requires B"). A cycle (A→B→A) makes every course in the loop permanently un-enrollable, so we reject it at *add* time. Before inserting "course requires prerequisite", walk the requirement graph starting from the prerequisite node with a **recursive CTE**; if it can already reach the course, adding the edge would close a loop → reject with `409`. A composite primary key blocks duplicate edges and a `CHECK (course_id <> prerequisite_id)` blocks the trivial self-loop, both at the DB level. Enrollment is then gated on *completion* of every prerequisite (not mere enrollment), checked inside the same `SELECT … FOR UPDATE` enrollment transaction — non-empty unmet set → `422`.

### Q: Why cache the course catalog with a "generation" number instead of just deleting the keys?

**A:** The catalog is paginated (`GET /courses?limit&offset`), so it's cached as many keys — `course:catalog:v{N}:{limit}:{offset}`. When a publish/update/archive changes which courses are published, *every* page is potentially stale. Deleting them would mean a `SCAN`+`DEL` over an unknown key set (slow, discouraged in prod). Instead we keep a generation counter `course:catalog:version` and a single `INCR` invalidates all pages at once — old keys become unreachable and expire by TTL. Course *detail* is simpler: one key per course (`course:detail:{id}`), deleted directly on change. Only **published** courses are cached — draft/archived visibility depends on the viewer, so caching them keyed by id alone would leak. The whole cache is best-effort: a short connect timeout + a cooldown circuit breaker mean a Redis outage degrades to Postgres reads, never an error.

### Q: For recommendations, why count popularity in Postgres instead of the Mongo event log?

**A:** Popularity must be an *exact* count, and Postgres `enrollments` is the source of truth. The Mongo `events` collection is a raw at-least-once interaction log — a redelivered `user.enrolled` appears twice, so counting there over-reports. Per our own tool-responsibility split (Postgres = consistency/truth, Mongo = analytics/behavioral log), the exact "most-enrolled" ranking is a Postgres `GROUP BY`. The Mongo log is the right source for *behavioral* signals instead — e.g. "students who took X also took Y" collaborative filtering — which is the natural next iteration. Recommendations also reuse the prerequisite graph: only courses whose prerequisites the student has completed are surfaced.

### Q: Why an in-app schema gate instead of standing up the Confluent Schema Registry container?

**A:** The value of a Schema Registry for this single-team system is the *contract discipline* — versioned event schemas + a compatibility rule enforced at the producer — not the Confluent infrastructure (which earns its keep when independent teams share topics). So we built that discipline in-process: `app/events/schema_registry.py` registers a schema per event, `validate()` rejects a malformed payload at emit time (mirroring SR rejecting an incompatible produce), and `is_backward_compatible()` encodes the BACKWARD rule (drop field / add optional = OK; add required / change type = rejected) with tests. Standing up Confluent SR + Avro is then a serialization swap at the relay, not a redesign — deliberately deferred as the lowest-ROI of the four features for a system where we own every producer and consumer.

### Q: How were the deferred features verified, and why test that way?

**A:** Each behavioural claim is encoded as a test (cycle → 409, unmet prereq → 422, stale cache busted on update, breaking schema change rejected). Two kinds:

- **Integration tests** (real app + real Postgres + real Redis) for anything that depends on engine-specific behaviour — recursive CTEs, `SELECT … FOR UPDATE`, JSONB, generational cache keys. A SQLite stand-in would prove nothing because those features don't exist there.
- **Pure unit tests** for the schema registry — validation and BACKWARD-compatibility are plain functions, no I/O needed.

Two test-infra decisions worth noting: (1) a **Temporal-free direct-publish helper** creates a published course by flipping status in the DB, instead of running the real publish workflow — which would drag in the Week-4 embedding pipeline (torch). Prereq/cache/recommendation tests need a *published course to exist*, not the publish mechanism, so this is both faster and better isolation (the workflow has its own test). (2) The cache is **disabled by default under test** (a Redis instance outlives the per-test DB resets and would leak data across tests); one dedicated test re-enables it to prove caching + invalidation. The Alembic migration is verified separately (apply → check constraints → downgrade → re-apply) because the test schema is built with `create_all`, which never exercises the migration.

### Q: How does a Kafka Schema Registry actually work (mechanics + compatibility modes)?

**A:** It's a separate HTTP service beside Kafka (the broker itself only sees bytes — it knows nothing about schemas). The client-side serializers/deserializers talk to it.

**Wire mechanics:** you register a schema (usually Avro) per topic "subject"; each version gets an integer **ID**. A produced message is `[magic byte][4-byte schema ID][binary payload]` — the schema is *not* in the message, only its ID. So messages are small (no repeated JSON keys) and self-identifying. Consumers read the ID, fetch that schema (cached), and decode; having both writer and reader schemas, Avro reconciles differences (defaults, skipped fields).

**Compatibility modes** (checked when registering a new version; the mode reflects deployment order, since old+new run together during a rollout):

| Mode | Guarantee | Upgrade first | May / may not |
|---|---|---|---|
| BACKWARD (default) | new reads old data | consumers | delete field, add optional ✅ / add required, change type ❌ |
| FORWARD | old reads new data | producers | add field, delete optional ✅ |
| FULL | both | either | optional add/delete only |
| NONE | nothing | — | anything (risky) |

A breaking change (e.g. rename `student_id`→`user_id` = drop a field + add a required one) is **rejected at registration** under BACKWARD, so the producer fails to deploy rather than breaking consumers silently in prod. The safe version is multi-step: add `user_id` optional → migrate consumers → backfill → remove `student_id`. See the earlier entry for why we deferred the Confluent service and mirror just the gate in-app.

### Q: When do you actually need a Schema Registry vs. when is it overkill?

**A:** The registry mainly defends against a schema change that *doesn't go through a single review*. So:

**Need it when** — (1) **multiple teams/services share a topic** (no single PR fixes all consumers; the registry is the enforced contract + coordination point); (2) **polyglot consumers** (Java + Python + Go on one topic — no shared language type, so you need a language-neutral contract); (3) **long-lived events / event sourcing / long retention** (a consumer may replay an event written many versions ago → need compatibility across all history, via `*_TRANSITIVE`); (4) **formal governance/compliance** (auditable, versioned record of data contracts).

**Overkill when (SmartCourse today)** — single codebase (a field rename is ONE PR touching producer + all consumers atomically — the "changed without telling the readers" failure can't happen); one team; you control + co-deploy every producer and consumer; only three event types. Pydantic/Zod validation at emit + a `schema_version` field is ~80% of the safety (catches malformed/typo'd payloads) for ~5% of the effort (no service, no Avro, no serialization rewrite). The missing 20% — automatic cross-version enforcement, cross-team/cross-language store, binary wire format, governance trail — doesn't pay off until a second team/non-Python consumer/long retention appears. Migration path then is a serialization swap at the relay, not a redesign.

### Q: Explain each Schema Registry compatibility mode in detail (with deploy order).

**A:** The mode encodes which direction must survive a rollout, which dictates deploy order (old + new always coexist mid-rollout). Running example `user.enrolled` v1 = `{enrollment_id, student_id, course_id, enrolled_at?}`.

- **BACKWARD** (default): new schema reads old data → upgrade **consumers first**. Allowed: delete a field; add an *optional* field (needs a default). Rejected: add a *required* field; change a type. E.g. add `source` optional ✅, remove `enrolled_at` ✅, add required `tenant_id` ❌. Use it ~90% of the time: you grow the event with optional fields and drop fields freely.
- **FORWARD**: old schema reads new data → upgrade **producers first**. Allowed: add a field (even required — old consumer ignores it); delete an *optional* field. Rejected: delete a *required* field; change a type. (Adding a required field being OK here but not under BACKWARD is the clearest proof that direction matters.)
- **FULL**: both directions → any deploy order. Effectively only *optional add / optional delete* survive. Safest, strictest.
- **NONE**: no checks — manage compatibility out-of-band; risky as a default.
- **`_TRANSITIVE` variants**: check against *every* prior version, not just the latest. Needed when old data persists (long retention, replays, event sourcing) so a consumer might hit any historical version; non-transitive is fine when old messages age out before you evolve again.

Caveat: changing a field type is unsafe in all modes except Avro's narrow promotions (`int→long`, `float→double`). A rename = delete-old + add-new (optionally with Avro `aliases`), which is why renames so often trip the compatibility check.

### Q: What do p50 / p95 / p99 mean in the load baseline, and why record all three?

**A:** Sort every request from fastest to slowest; a percentile is the time at the X% mark. **p50** (median) = the typical request (half faster, half slower). **p95** = only the slowest 5% were worse. **p99** = only the worst 1% were worse.

Why not the average? The average *hides* the slow tail — 99 requests at 20 ms + 1 at 2000 ms averages to ~40 ms (looks fine) while one user waited 2 s; p99 catches it. The tail matters because at scale 1% is huge (1M req/day → 10k slow/day) and it compounds per user (a page firing 20 calls, each 1% slow, ≈ 18% chance of one slow call).

Each answers a different question: p50 = "what's normal?", p95 = "the common bad case" (typical SLO target), p99 = "how bad is the tail?" (cold caches, lock waits, slow query plans). **The p50→p99 gap = consistency.** In our [LOAD_BASELINE.md](LOAD_BASELINE.md): `metrics/overview` 25→45 ms (tight, steady) vs `recommendations` 26→638 ms (24× gap → the uncached heavy query makes a minority of requests slow → the thing to watch).

---

## Session — 2026-06-11 (System-design deep-dive review)

### Q: Difference between strong and eventual consistency — and where does SmartCourse use each?

**A:** **Strong** = the instant a write is confirmed, every later read (anyone) sees it; there's one agreed "current value." **Eventual** = reads may be stale for a window, but converge once writes stop.

**Why strong exists — the seat race:** course has 1 seat; A and B enrol simultaneously. Without coordination both read "1 left", both pass, both insert → oversold (corrupt state). With `SELECT … FOR UPDATE` the lock serialises them: A enrols (seats→0), B is blocked then reads 0 → rejected. "Guaranteed to see the latest" *is* strong consistency.

**Why eventual is fine — the counter:** an enrolment's `user.enrolled` event updates the analytics total a few seconds later; an admin refreshing mid-window sees the old number, no one harmed, it converges.

**The tradeoff:** strong needs coordination (a lock, a single source of truth, or consensus) → slower and unavailable during a partition (CAP). Eventual drops coordination → fast, available, scalable, correct-soon.

**Decision rule:** "if a reader sees a stale value for a few seconds, is anyone harmed / does the system become incorrect?" Yes → strong (seats, balances, identity). No → eventual (counts, emails, caches).

**In SmartCourse:** strong for enrolment+capacity (`FOR UPDATE`), `UNIQUE` dedupes, draft→published; eventual for analytics, welcome email, cached catalog/detail, recommendations, search index. The **outbox** bridges them — the enrolment row + the event commit in one transaction (strong, atomic), then the fact fans out eventually to Kafka consumers. The cache widened the eventual zone on reads (catalog stale up to its 30s TTL) — a conscious speed-for-freshness trade; caching a *seat count* would be a bug (making a strong fact eventual).

**Caveat:** "consistency" here is the CAP/replication sense (do readers agree on the latest value?), *not* ACID's "C" (single-node constraint validity). `FOR UPDATE` happens to give both.

### Q: Case 2 — Fault tolerance: the "exactly-once myth", DLQs, and what belongs in a critical path?

**A:** Fault tolerance = recovering to a correct state without a human when (not if) something fails.

**Exactly-once is a myth across systems.** You can't atomically commit Kafka offset + Postgres + RabbitMQ together, so you choose: at-most-once (ack then process → loss on crash) or at-least-once (process then ack → duplicate on crash). "Exactly-once" = at-least-once + an **idempotent consumer**. Our `welcome_email_consumer` does this deliberately: claim via `INSERT … ON CONFLICT DO NOTHING` on `(consumer, event_key)`, do work, COMMIT Postgres, *then* commit the Kafka offset. The dedupe row IS the idempotency key, and committing it before the offset makes every crash window safe (a 4→5 crash gives a duplicate task the idempotent task absorbs; a 5→6 crash gives exactly-once). It consciously prefers duplicate-over-lost. (Same pattern as deduping Stripe webhooks on event id.)

**Missing DLQ = a liveness bug.** At-least-once + idempotency only handles *transient* faults. A *poison* message (corrupt bytes, always-throws) gets no offset commit → Kafka redelivers forever → because a partition is ordered, it **blocks everything behind it (head-of-line blocking)**. Fix: after N attempts route to a dead-letter topic/table, commit the offset, move on, alert. Tradeoff: give up one message to keep the pipeline flowing. Rule: *retry handles transient, DLQ handles permanent* — a retry loop with no DLQ/max-retries stalls the stream.

**Durable ≠ belongs-in-the-critical-path.** The publish saga runs embedding (`process_lessons_activity`, torch) *inside* the compensated Temporal workflow, so an ML hiccup **reverts the publish to draft** — an optional feature breaking a core action (and it contradicts our own "content processing → async" rule). Temporal's durability tempted the critical path wider. Better: mark `published` immediately, index *after* as a separate async job (`indexed_at` when done) — a short "published, indexing…" window that harms no one. Rule: the critical path holds only what MUST be true for the op to be correct; for each step ask *"if this failed forever, should the whole operation fail?"* — if no, it's eventual async work outside the path. Ties to Case 1: indexing is eventual-consistency work wrongly placed inside a strong-consistency operation.

### Q: In plain words — what's a DLQ? And in Design B, how does a user search a published-but-not-yet-embedded course?

**A:** **DLQ (dead-letter queue)** = the "undeliverable mail bin." A permanently-broken message retried forever blocks every message ordered behind it on the partition (**head-of-line blocking** — a stalled car in a one-lane tunnel). After N tries you park it in a side topic/table, commit the offset, keep the pipeline flowing, and review it later.

**Embedding-in-publish (plain):** publish runs a checklist and undoes everything if any step fails; the slow/fragile AI embedding step is in that checklist, so an AI hiccup cancels the whole publish — an optional "make it searchable" extra breaking the core action.

**The Design B objection answered:** embedding takes the same time in *both* designs — the only difference is what the user can do during that unavoidable wait. Design A: course fully hidden (can't view/enroll/learn/search). Design B: course fully usable, only search briefly delayed. So Design B gives *more*, not less. Handle the gap with an "indexing…" state (`indexed_at = null` until done), like YouTube's "HD still processing" while the video already plays. Principle: **no free lunch — choose which downside you can live with**; a briefly-delayed *optional* feature beats a *failing core action*.

### Q: What are the design patterns we're studying called?

**A:** Consistency: **CAP theorem**, **strong vs eventual consistency**, **CQRS** (separate write model from read model). Fault tolerance: **transactional outbox**, **idempotent consumer**, **delivery semantics** (at-most/at-least/"exactly"-once = at-least-once + idempotency), **dead-letter queue**, **head-of-line blocking**, **Two Generals / distributed-commit problem**, **saga + compensating transactions**, **circuit breaker**.

### Q: Case 3 — Scalability: where does SmartCourse hit a wall, and how do you scale around it?

**A:** Scalability = still works at 10×/100×. Find the one thing every request must touch — that's the ceiling.

**Scales easily:** the API is **stateless** (JWT carries identity) → add boxes behind a load balancer, any copy serves any request. **Kafka** is a shock absorber — a write spike commits to Postgres + outbox, and email/analytics consumers drain at their own pace.

**Hits a wall — all at the single Postgres primary:**
1. **Connection-pool cliff (an outage, not a slowdown):** `pool_size=10 + max_overflow=20` = 30/copy × 4 gunicorn workers = 120 > Postgres' default 100 → it *refuses* new connections. Fix: **PgBouncer** multiplexes hundreds of app connections onto ~20 real ones (tradeoff: transaction mode disallows some session features).
2. **Hot-course lock serialization:** `FOR UPDATE` (the Case-1 correctness win) serializes every enrollment to one popular course through a single row lock. Fixes: optimistic concurrency (retry on conflict) or an atomic Redis seat counter (fast, but seats now live in two places → reconciliation, Redis becomes a correctness dependency). `FOR UPDATE` is the right default — only change if a measured spike hurts.
3. **No read replica:** heavy analytics aggregations run on the same primary as live enrollments (OLTP vs OLAP contention). Fix: a read replica for analytics reads; tradeoff = replication lag (slightly stale dashboards, which is fine — eventual reads).
4. **Recommendations tail** (measured p99 ~640ms): the one uncached heavy query; fix = short-TTL per-student cache.

**Unifying insight:** one stateful chokepoint (the Postgres primary) — every scaling move routes load *around* it (PgBouncer, read replica, Redis counter, caching). **Ladder:** vertical (bigger box) → horizontal (more boxes; API yes, single primary no) → read replicas (scale reads) → sharding (split writes across primaries; last resort, big complexity). Patterns: connection pooling, OLTP vs OLAP, read replica, replication lag, vertical/horizontal scaling, sharding, optimistic vs pessimistic concurrency.

### Q: How is "1k → 1M requests" handled, and what hardware does a million need?

**A:** "1 million requests" is meaningless without a timeframe — the unit is **requests/sec (RPS)**: 1M/day ≈ 12/s (trivial), 1M/hour ≈ 280/s (one box), 1M/min ≈ 16,600/s (cluster), 1M/sec = Google-scale. Restaurant model: **API servers = waiters (easy to add); Postgres = the one kitchen (the bottleneck); Redis = a tray of ready dishes**. Ladder: ≤1k/s = one server + cache; 1k–10k/s = many stateless API boxes + load balancer + PgBouncer + cache + read replica; 10k–100k/s = autoscaled API + bigger/sharded DB; 1M/s = re-architect (fleet + sharded, multi-region). Measured: ~400 req/s per worker (DB endpoint, 0 errors), ~1k+/s per 4-worker box. Hardware for "a million": per *day* → tiny VM; per *hour* → one 4-CPU/8GB box + managed PG; per *minute* → ~10–20 API instances + PgBouncer + 8–16-CPU/32–64GB PG + replicas + Redis. **Which requests slow down:** the overflow that exceeds a resource queues, and the *tail* (p95/p99) degrades first (e.g. 120 requests vs 100 connections → ~20 wait).

### Q: What is connection pooling (easy), and how much traffic can a normal DB handle?

**A:** A **connection** is an expensive dedicated "phone line" to Postgres (handshake + auth + the DB spawns a process using a few MB). Opening one per request is wasteful. **Pooling** keeps a small set of warm lines and reuses them: borrow → query → return (don't hang up). Two wins: **speed** (skip setup) and **protection** (a hard cap on simultaneous connections; when the pool is full, extra requests *wait* — those are the slow ones). Our config: `pool_size=10` warm + `max_overflow=20` burst + `pool_pre_ping` (check the line is alive). Same as `pg.Pool`/Prisma/TypeORM `max`.

**How much a normal DB handles** — key insight: requests/s ≠ queries/s ≠ connections. One connection = one checkout lane running *many* fast queries/sec, so you need a *handful* of fast lanes, not thousands. Ballparks on a standard 4–8-CPU SSD box (indexed + cached): simple reads ~10k–30k/s, simple writes ~2k–10k/s, complex joins/aggregations ~hundreds–low-thousands/s. Counterintuitive: **more connections past ~2–4× CPU cores makes it slower** (context-switch thrash) — that's why pooling caps it and PgBouncer funnels thousands of clients onto ~20–50 server connections. **Indexes + caching matter more than hardware** (a missing index = 100× slower). SmartCourse's ~400 req/s/worker already implies a real PG box serves tens of thousands of daily users — nowhere near the ceiling.
