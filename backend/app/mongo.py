"""Async MongoDB client + helpers.

MongoDB's job in this project is the **raw interaction/event log** — the
storage decision recorded in docs/QA.md ("Final storage architecture").
PostgreSQL stays the source of truth for users, courses, enrollments,
progress, and (in Week 4) chunks + embeddings via pgvector. MongoDB holds
the high-volume, append-only stream of events that the analytics layer
queries and that future ML/recommendations consume.

One client per process, one database, one collection (`events`). Indexes
are created on first start of the consumer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase


_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """Lazy-init a single Motor client for the lifetime of the process."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_url)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongo_db]


def get_events_collection() -> AsyncIOMotorCollection:
    return get_db()["events"]


async def init_indexes() -> None:
    """Idempotent — safe to call on every consumer startup."""
    coll = get_events_collection()
    # Business identity — uniqueness here gives us a second line of defense
    # behind the processed_events Postgres dedupe.
    await coll.create_index("event_key", unique=True)
    # Filter-by-type is the most common analytics access pattern.
    await coll.create_index("event_type")
    # Time-range queries (e.g. "enrollments in the last hour") sort by this.
    await coll.create_index([("kafka.timestamp_ms", -1)])
