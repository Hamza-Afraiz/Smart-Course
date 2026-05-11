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
