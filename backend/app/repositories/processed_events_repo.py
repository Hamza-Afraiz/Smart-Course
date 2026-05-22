from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processed_event import ProcessedEvent


async def claim(db: AsyncSession, *, consumer: str, event_key: str) -> bool:
    """Mark (consumer, event_key) as processed if it hasn't been before.

    Returns True on first call (the consumer should now do its side effect),
    False on every subsequent call (duplicate — skip).

    Uses `RETURNING` because `result.rowcount` after `INSERT ... ON CONFLICT
    DO NOTHING` is not consistently reported across drivers (psycopg3 in
    particular can report 0 even on a successful insert). The presence of a
    returned row is the authoritative signal.
    """
    stmt = (
        insert(ProcessedEvent)
        .values(consumer=consumer, event_key=event_key)
        .on_conflict_do_nothing(index_elements=["consumer", "event_key"])
        .returning(ProcessedEvent.event_key)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
