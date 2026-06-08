"""Outbox relay — drains the Postgres `outbox` table into Kafka.

Long-running poller (a BullMQ-style worker, not a cron). One iteration:

  1. Open a transaction.
  2. Claim a batch of unsent rows with `FOR UPDATE SKIP LOCKED`.
  3. Publish each to its Kafka topic in parallel (`acks=all`).
  4. Bulk-UPDATE `sent_at` on the same rows.
  5. COMMIT — releases row locks.

Failure modes & guarantees:
  - Kafka unreachable      → `send_and_wait` raises; transaction rolls back;
                             rows stay `sent_at IS NULL`; retried next tick.
                             **No event loss.**
  - Process crash mid-tick → uncommitted UPDATEs disappear when the connection
                             drops; on restart the same rows are claimed again.
                             A duplicate Kafka publish is possible if the crash
                             was after `send_and_wait` returned but before
                             COMMIT — caught downstream by consumer dedupe
                             (event_key idempotency).
  - Multiple replicas      → `SKIP LOCKED` partitions work across instances.
  - Empty outbox           → short `IDLE_SLEEP_SEC` sleep, then loop.

Delivery: **at-least-once** out of the relay, **effectively-once** end-to-end
once paired with consumer-side dedupe on `event_key`.

Run as a separate docker-compose service off the `smart-course-app` image:
    command: ["watchfiles", "python -m app.workers.outbox_relay", "app"]
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer

from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories import outbox_repo

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
IDLE_SLEEP_SEC = 0.5
ERROR_BACKOFF_SEC = 2.0


def _topic_for(event_type: str) -> str:
    # Per-event-type topic so each consumer can subscribe to just what it needs.
    # Dot-namespaced is a Kafka idiom: events.user.enrolled, events.lesson.completed, ...
    return f"events.{event_type}"


async def _publish_one(producer: AIOKafkaProducer, row) -> None:
    """Send one outbox row to Kafka, waiting for the ack."""
    await producer.send_and_wait(
        topic=_topic_for(row.event_type),
        # Key drives Kafka partitioning — same business event always lands on
        # the same partition, preserving per-entity ordering. Also doubles as
        # the consumer-side idempotency key.
        key=row.event_key.encode(),
        value=json.dumps(row.payload).encode(),
        headers=[
            ("idempotency_key", row.event_key.encode()),
            ("event_type", row.event_type.encode()),
            ("outbox_id", str(row.id).encode()),
        ],
    )


async def _run_one_tick(producer: AIOKafkaProducer) -> int:
    """One claim → publish → mark cycle. Returns rows handled this tick."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            rows = await outbox_repo.claim_unsent_batch(session, limit=BATCH_SIZE)
            if not rows:
                return 0

            # Parallelise the Kafka roundtrips within a batch. Row locks are
            # held for the duration of the gather; with acks=all on a healthy
            # cluster this is tens of milliseconds for ~100 rows.
            await asyncio.gather(*(_publish_one(producer, r) for r in rows))

            await outbox_repo.mark_sent(
                session,
                ids=[r.id for r in rows],
                sent_at=datetime.now(timezone.utc),
            )
            return len(rows)
        # COMMIT happens here on clean exit; ROLLBACK on any exception above.


async def _run() -> None:
    from app.observability.logging import configure_json_logging
    from app.observability.tracing import configure_tracing, instrument_sqlalchemy
    from app.observability.metrics_server import start_metrics_server
    from app.database import engine
    configure_json_logging(service_name="outbox-relay")
    configure_tracing(service_name="outbox-relay")
    instrument_sqlalchemy(engine)
    start_metrics_server()  # Prometheus scrapes :9100 → up{job="relay"}
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        acks="all",                  # wait for all in-sync replicas (durability)
        enable_idempotence=True,     # producer-side dedupe across its own retries
        client_id="outbox-relay",
    )
    await producer.start()
    logger.info(
        "outbox-relay: connected to Kafka at %s — polling outbox every %.1fs when idle",
        settings.kafka_bootstrap_servers,
        IDLE_SLEEP_SEC,
    )

    try:
        while not stop_event.is_set():
            try:
                n = await _run_one_tick(producer)
                if n > 0:
                    logger.info("outbox-relay: published %d events", n)
                    continue  # immediately look for more — drain fast under load
            except Exception:
                logger.exception("outbox-relay: tick failed; backing off")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=ERROR_BACKOFF_SEC)
                except asyncio.TimeoutError:
                    pass
                continue

            # idle — short sleep, interruptible by shutdown signal
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=IDLE_SLEEP_SEC)
            except asyncio.TimeoutError:
                pass
    finally:
        await producer.stop()
        logger.info("outbox-relay: stopped cleanly")


if __name__ == "__main__":
    asyncio.run(_run())
