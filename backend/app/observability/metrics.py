"""Custom Prometheus metrics — business-level counters and histograms.

These complement the auto-instrumented HTTP metrics from
`prometheus-fastapi-instrumentator`. The standard `/metrics` endpoint on
the API serves both.

Naming follows Prometheus conventions:
  - snake_case
  - `_total` suffix for monotonic counters
  - `_seconds` suffix for time durations
  - label names lowercase, no high-cardinality values
"""

from prometheus_client import Counter, Histogram

# ── Business counters ────────────────────────────────────────────────────────

events_emitted_total = Counter(
    "smartcourse_events_emitted_total",
    "Domain events emitted (written into the outbox or sent direct to Kafka)",
    ["event_type", "path"],   # path = "outbox" | "direct" — separates the two emission paths
)

events_archived_total = Counter(
    "smartcourse_events_archived_total",
    "Events written to the MongoDB `events` collection by the archiver",
    ["event_type"],
)

events_consumed_total = Counter(
    "smartcourse_events_consumed_total",
    "Messages handled by a Kafka consumer (by outcome)",
    ["consumer", "event_type", "outcome"],   # outcome = "enqueued" | "duplicate" | "error"
)

outbox_published_total = Counter(
    "smartcourse_outbox_published_total",
    "Outbox rows successfully published to Kafka by the relay",
    ["event_type"],
)


# ── Histograms ───────────────────────────────────────────────────────────────

outbox_latency_seconds = Histogram(
    "smartcourse_outbox_latency_seconds",
    "Time from outbox INSERT to Kafka send (excludes consumer lag)",
    ["event_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
