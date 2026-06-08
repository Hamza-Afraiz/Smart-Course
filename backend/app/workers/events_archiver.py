"""Events archiver — the universal Kafka consumer.

Subscribes to **every** `events.*` topic and writes each message into
MongoDB's `events` collection. This is the raw interaction log; the
analytics layer queries it (alongside the Postgres core tables) to build
the dashboard metrics defined in the PRD.

Two layers of duplicate protection:
  1. `processed_events_repo.claim(consumer="events-archiver", ...)` —
     PostgreSQL PRIMARY KEY rejects any second insert for the same key.
  2. Mongo's unique index on `event_key` — even if the Postgres dedupe
     somehow missed it, the Mongo upsert is naturally idempotent because
     we use `$setOnInsert`.

Failure-mode ordering — same as welcome-email consumer:
    receive → claim (PG TX) → write Mongo → commit PG TX → commit Kafka offset

  - Crash mid-TX before Mongo write: redelivery, claim succeeds, retry.
  - Crash after Mongo write before PG commit: rollback dedupe;
    redelivery → claim succeeds → Mongo `$setOnInsert` no-ops on the
    existing doc → safe. (This is why $setOnInsert is important — plain
    `update` would overwrite.)
  - Crash after PG commit before Kafka commit: redelivery → claim fails →
    skip. Mongo already has the doc.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.database import AsyncSessionLocal
from app.mongo import get_events_collection, init_indexes
from app.repositories import processed_events_repo

logger = logging.getLogger(__name__)

CONSUMER_NAME = "events-archiver"
TOPICS = [
    "events.user.enrolled",
    "events.lesson.completed",
    "events.course.published",
]


def _header(headers, name: str) -> str | None:
    for k, v in headers or []:
        if k == name:
            return v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
    return None


async def _archive(msg) -> str:
    """Process one Kafka message. Returns a short status for logging."""
    event_key = _header(msg.headers, "idempotency_key")
    event_type = _header(msg.headers, "event_type")
    if not event_key or not event_type:
        return f"missing-headers (topic={msg.topic} offset={msg.offset})"

    try:
        payload = json.loads(msg.value)
    except json.JSONDecodeError:
        # Don't keep retrying garbage — still mark it processed and skip
        logger.warning("events-archiver: non-JSON value on %s offset=%d", msg.topic, msg.offset)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await processed_events_repo.claim(
                    session, consumer=CONSUMER_NAME, event_key=event_key
                )
        return f"bad-json {event_key}"

    # Claim first (Postgres), then upsert to Mongo, then commit Postgres.
    async with AsyncSessionLocal() as session:
        async with session.begin():
            claimed = await processed_events_repo.claim(
                session, consumer=CONSUMER_NAME, event_key=event_key
            )
            if not claimed:
                return f"duplicate {event_key}"

            doc = {
                "event_key": event_key,
                "event_type": event_type,
                "payload": payload,
                "kafka": {
                    "topic": msg.topic,
                    "partition": msg.partition,
                    "offset": msg.offset,
                    "timestamp_ms": msg.timestamp,
                },
                "archived_at": datetime.now(timezone.utc),
            }
            # $setOnInsert makes this a no-op when the doc already exists —
            # belt-and-suspenders alongside the Postgres claim.
            coll = get_events_collection()
            await coll.update_one(
                {"event_key": event_key},
                {"$setOnInsert": doc},
                upsert=True,
            )
            return f"archived {event_type} {event_key}"


async def _run() -> None:
    from app.observability.logging import configure_json_logging
    from app.observability.tracing import configure_tracing, instrument_sqlalchemy
    from app.observability.metrics_server import start_metrics_server
    from app.database import engine
    configure_json_logging(service_name="events-archiver")
    configure_tracing(service_name="events-archiver")
    instrument_sqlalchemy(engine)
    start_metrics_server()  # Prometheus → up{job="events-archiver"}

    await init_indexes()
    logger.info("events-archiver: Mongo indexes ready")

    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_NAME,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        client_id=CONSUMER_NAME,
    )
    await consumer.start()
    logger.info(
        "events-archiver: subscribed to %s on %s",
        ", ".join(TOPICS), settings.kafka_bootstrap_servers,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        async for msg in consumer:
            if stop_event.is_set():
                break
            try:
                status = await _archive(msg)
                await consumer.commit()
                logger.info(
                    "events-archiver: %s (topic=%s partition=%d offset=%d)",
                    status, msg.topic, msg.partition, msg.offset,
                )
            except Exception:
                # No commit → Kafka redelivers next poll. The dedupe + upsert
                # design absorbs the redelivery cleanly.
                logger.exception(
                    "events-archiver: failed processing topic=%s offset=%d — will redeliver",
                    msg.topic, msg.offset,
                )
                await asyncio.sleep(1.0)  # small backoff against poison messages
    finally:
        await consumer.stop()
        logger.info("events-archiver: stopped cleanly")


if __name__ == "__main__":
    asyncio.run(_run())
