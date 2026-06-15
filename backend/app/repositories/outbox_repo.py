from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import OutboxEvent


async def enqueue(
    db: AsyncSession,
    *,
    event_type: str,
    event_key: str,
    payload: dict[str, Any],
    traceparent: str | None = None,
) -> OutboxEvent:
    """Stage an event for the relay. Caller's transaction owns the commit —
    the row is only durably present once the caller's TX commits, which is
    exactly the atomicity guarantee we want.
    """
    event = OutboxEvent(
        event_type=event_type,
        event_key=event_key,
        payload=payload,
        traceparent=traceparent,
    )
    db.add(event)
    await db.flush()
    return event


async def claim_unsent_batch(
    db: AsyncSession, *, limit: int
) -> list[OutboxEvent]:
    """Lock and return a batch of unsent rows for the relay.

    `FOR UPDATE SKIP LOCKED` makes this safe to run with N replicas — each
    relay instance gets a disjoint batch instead of blocking on the same rows.
    Locks release on COMMIT of the caller's transaction.
    """
    result = await db.execute(
        select(OutboxEvent)
        .where(OutboxEvent.sent_at.is_(None))
        .order_by(OutboxEvent.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(result.scalars().all())


async def mark_sent(
    db: AsyncSession, *, ids: list[int], sent_at: datetime
) -> None:
    """Bulk-stamp `sent_at` on a batch of outbox rows. One UPDATE for the lot."""
    if not ids:
        return
    await db.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id.in_(ids))
        .values(sent_at=sent_at)
    )
