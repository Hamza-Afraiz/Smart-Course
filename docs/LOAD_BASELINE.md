# Load baseline (NFR-P03)

A recorded snapshot of latency + throughput per hot endpoint, so a regression is
visible after a change. Re-run after anything that touches a query, an index, the
cache, or the connection pool.

## How to run

Stack must be up (`docker compose up -d`), then from the repo root:

```bash
venv/bin/python scripts/load_baseline.py
# or against another host:
BASE=http://localhost:8000 venv/bin/python scripts/load_baseline.py
```

Self-contained (only needs httpx, already in the backend venv). It logs in as the
seed admin + a load-test student, warms each endpoint, then fires N requests at a
fixed concurrency and reports p50/p95/p99 + req/s. A `hey`-based shell variant
lives at `scripts/load_baseline.sh` (needs `go install …/hey`).

## Latest baseline

**2026-06-11 · local Docker · single uvicorn worker · Postgres + Redis up · cache enabled**

| Endpoint | n | c | p50 (ms) | p95 (ms) | p99 (ms) | req/s | errors |
|----------|---|---|----------|----------|----------|-------|--------|
| `GET /health` | 300 | 30 | 25.1 | 99.3 | 147.3 | 774 | 0 |
| `GET /api/v1/courses` (cached catalog) | 200 | 20 | 36.1 | 140.9 | 173.6 | 402 | 0 |
| `GET /api/v1/courses/recommendations` | 100 | 10 | 26.2 | 636.1 | 638.5 | 113 | 0 |
| `GET /api/v1/admin/metrics/overview` | 100 | 10 | 25.0 | 38.2 | 44.8 | 371 | 0 |

### Reading this

- **No errors** under concurrency on any endpoint — routing, auth, and the
  connection pool all hold.
- **`recommendations` is the watch item.** p50 is fine (26 ms) but the tail blows
  out to ~640 ms (p95/p99). It's the heaviest query — published filter + two
  `NOT IN` subqueries (already-enrolled, prereq-blocked) + `GROUP BY` + outer join
  to `enrollments` for the popularity count — and it is **not cached**. If this ever
  became a hot path the fix is a short-TTL per-student cache or a materialized
  popularity rollup, *not* more indexes (the join columns are already indexed).
- `metrics/overview` is the tightest (p99 45 ms) — pure aggregate counts.
- `/health`'s tail (p99 147 ms) is single-worker event-loop contention from a local
  load client at c=30, not a real concern; p50 (25 ms) is the true figure.

These are a **local, single-worker baseline**, not a production SLO. For SLOs: run
against a gunicorn deployment (`-w 4`) on representative hardware, with seeded data
volume, from a separate load machine.

## Session log

| Date | Environment | Notes |
|------|-------------|-------|
| 2026-06-11 | local docker, 1 uvicorn worker | initial baseline; recommendations tail flagged |

**Not in the script (run separately):** `POST /assistant/ask` (LLM-bound, seconds)
and `POST /courses/{id}/enroll` (DB row-lock path) — slower and variable; measure
those on their own when needed.
