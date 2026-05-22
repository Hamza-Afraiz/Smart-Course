"""MongoDB aggregations against the `events` collection.

This is the read side of the raw interaction log written by the
events-archiver consumer. Time-series queries and event-shape lookups
live here; SQL-shaped queries against current state live in metrics_repo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.mongo import get_events_collection


async def enrollments_per_day(*, days: int) -> list[dict]:
    """Histogram of `user.enrolled` events bucketed by calendar day (UTC)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    coll = get_events_collection()
    pipeline = [
        {"$match": {"event_type": "user.enrolled", "archived_at": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$archived_at"}
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    cursor = coll.aggregate(pipeline)
    return [doc async for doc in cursor]


async def recent_activity(*, limit: int) -> list[dict]:
    """Latest N events of any type — admin "what's happening" feed."""
    coll = get_events_collection()
    cursor = (
        coll.find({}, {"_id": 0})
        .sort("archived_at", -1)
        .limit(limit)
    )
    return [doc async for doc in cursor]
