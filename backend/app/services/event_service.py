"""High-level interface for emitting domain events.

Services call `emit(...)` after their business write; the event is staged in
the outbox in the *same* DB transaction. A separate relay process picks it up
and publishes to Kafka. This module hides the storage mechanism — callers
think in terms of events, not tables.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.events import schema_registry
from app.observability.metrics import events_emitted_total
from app.observability.propagation import inject_traceparent
from app.repositories import outbox_repo


async def emit(
    db: AsyncSession,
    *,
    event_type: str,
    event_key: str,
    payload: dict[str, Any],
) -> None:
    """Stage a domain event for at-least-once delivery to Kafka.

    Atomicity: the event is INSERTed into the outbox in the caller's open
    transaction — it commits together with the business write or not at all.
    No dual-write to Kafka happens at request time.

    Idempotency: `event_key` must be deterministic from the business row
    (e.g. f"enrollment-{enrollment_id}"). Consumers dedupe on it so retries
    on the relay → Kafka leg don't cause double side-effects downstream.
    """
    # Producer-side contract gate — reject a malformed payload before it is
    # staged. Same role as a Schema Registry rejecting an incompatible produce.
    schema_registry.validate(event_type, payload)

    await outbox_repo.enqueue(
        db,
        event_type=event_type,
        event_key=event_key,
        payload=payload,
        traceparent=inject_traceparent(),
    )
    # path="outbox" — distinguishes these from `direct` Kafka publishes from
    # inside a Temporal activity (course.published).
    events_emitted_total.labels(event_type=event_type, path="outbox").inc()
