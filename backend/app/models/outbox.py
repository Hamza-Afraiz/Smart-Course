from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OutboxEvent(Base):
    """Transactional outbox.

    Producer-side durability for event emission: rows are inserted in the same
    Postgres transaction as the business write (e.g. an enrollment), so the
    "did we record this event?" question collapses into a single atomic commit
    rather than a dual-write across Postgres + Kafka.

    A relay process polls `WHERE sent_at IS NULL`, publishes to Kafka, and
    marks the row sent. Until then the row sits durably in Postgres — a relay
    crash, a Kafka outage, anything short of Postgres data loss is recoverable.
    """

    __tablename__ = "outbox"
    __table_args__ = (
        # Partial index keeps the relay's "fetch unsent" query O(unsent) even
        # as the table grows — the bulk of sent rows are skipped by the index.
        Index(
            "idx_outbox_unsent",
            "created_at",
            postgresql_where="sent_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # Business-level idempotency key — deterministic from the source row
    # (e.g. f"enrollment-{enrollment_id}"). Consumers dedupe on this.
    event_key: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # NULL = not yet published to Kafka. Set by the relay on successful send.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # W3C traceparent captured at emit time — relay forwards it in Kafka headers.
    traceparent: Mapped[str | None] = mapped_column(String(255))
