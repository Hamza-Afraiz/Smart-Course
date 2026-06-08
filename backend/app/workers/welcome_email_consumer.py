"""Kafka → Celery bridge consumer for `user.enrolled` → welcome email.

One long-running process. Subscribes to `events.user.enrolled` as a consumer
group, dedupes each message via the `processed_events` table, and (for new
messages only) enqueues the welcome-email Celery task onto RabbitMQ.

THE ATOMICITY PUZZLE — read carefully if you change this:

    Three systems are involved per message — Kafka (offset), Postgres
    (dedupe row), RabbitMQ (Celery task enqueue) — and they cannot share a
    transaction. We pick the **duplicate-task** failure mode over the
    **lost-task** one. Losing a welcome email is worse than sending two; the
    task itself is naturally idempotent (it just logs in this stub; real email
    would record its own send marker).

Per-message ordering:

    1. Receive message
    2. Open Postgres TX
    3. `processed_events_repo.claim()` → INSERT ON CONFLICT DO NOTHING
         - returned True  → we claimed the message; do the work
         - returned False → duplicate (delivery, rebalance, restart) — skip
    4. If claimed: enqueue Celery task (`.delay()` → RabbitMQ)
    5. COMMIT Postgres TX
    6. Commit Kafka offset

Failure modes:
    - Crash between 4 and 5: rollback wipes the dedupe row; on redelivery
      we claim again and re-enqueue → **duplicate task**. Idempotent task absorbs it.
    - Crash between 5 and 6: dedupe row committed but offset not; redelivery
      claims False and skips → task runs exactly once.
    - Crash before 5: no dedupe row, offset not committed → clean redelivery.

Multiple replicas safe (Kafka consumer-group partitions the work) and the
PRIMARY KEY on (consumer, event_key) closes any window where two replicas
race on the same message — only one INSERT wins.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from typing import Any

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories import processed_events_repo
from app.tasks.welcome_email import send_welcome_email

logger = logging.getLogger(__name__)

CONSUMER_NAME = "welcome-email"
TOPIC = "events.user.enrolled"


def _event_key_from(headers: list[tuple[str, bytes]] | None) -> str | None:
    for k, v in headers or []:
        if k == "idempotency_key":
            return v.decode()
    return None


async def _handle(msg) -> str:
    """Process one Kafka message. Returns a short status for the log line."""
    event_key = _event_key_from(msg.headers)
    if not event_key:
        return "missing-key"

    async with AsyncSessionLocal() as session:
        async with session.begin():
            claimed = await processed_events_repo.claim(
                session, consumer=CONSUMER_NAME, event_key=event_key
            )
            if not claimed:
                return f"duplicate {event_key}"

            payload: dict[str, Any] = json.loads(msg.value)
            enrollment_id = payload.get("enrollment_id")
            if not enrollment_id:
                # Don't enqueue garbage; still commit the dedupe row so we
                # don't keep retrying a malformed message forever.
                logger.warning("welcome-email: payload missing enrollment_id: %s", payload)
                return f"bad-payload {event_key}"

            # Enqueue inside the TX. If COMMIT fails after this, the task is
            # already on RabbitMQ; redelivery from Kafka would enqueue again.
            # That's the documented duplicate-task tradeoff.
            send_welcome_email.delay(enrollment_id)
            return f"enqueued {event_key} → enrollment={enrollment_id}"


async def _run() -> None:
    from app.observability.logging import configure_json_logging
    from app.observability.tracing import configure_tracing, instrument_sqlalchemy
    from app.observability.metrics_server import start_metrics_server
    from app.database import engine
    configure_json_logging(service_name="welcome-email-consumer")
    configure_tracing(service_name="welcome-email-consumer")
    instrument_sqlalchemy(engine)
    start_metrics_server()  # Prometheus → up{job="welcome-email-consumer"}

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_NAME,
        enable_auto_commit=False,        # we commit only after successful processing
        auto_offset_reset="earliest",    # new groups start from the topic's beginning
        client_id=CONSUMER_NAME,
    )
    await consumer.start()
    logger.info(
        "%s consumer: subscribed to %s on %s",
        CONSUMER_NAME, TOPIC, settings.kafka_bootstrap_servers,
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
                status = await _handle(msg)
                await consumer.commit()
                logger.info("welcome-email: %s (partition=%d, offset=%d)",
                            status, msg.partition, msg.offset)
            except Exception:
                # No commit → Kafka redelivers on next poll. Combined with the
                # processed_events dedupe, transient failures are safe.
                logger.exception(
                    "welcome-email: handler failed for offset=%d; will redeliver",
                    msg.offset,
                )
                # tiny backoff so we don't tight-loop on a poison message
                await asyncio.sleep(1.0)
    finally:
        await consumer.stop()
        logger.info("welcome-email consumer: stopped cleanly")


if __name__ == "__main__":
    asyncio.run(_run())
