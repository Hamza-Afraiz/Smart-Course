from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProcessedEvent(Base):
    """Consumer-side idempotency ledger.

    One row per (consumer, event_key) pair. Each consumer marks an event as
    handled before it does the side effect; a duplicate delivery (Kafka
    redelivery, consumer rebalance, relay retry) sees the row and skips.

    Composite PK on (consumer, event_key) so multiple consumer groups can
    independently dedupe the *same* Kafka message — `welcome-email` and
    `analytics` each see every message exactly once.
    """

    __tablename__ = "processed_events"

    consumer:     Mapped[str]      = mapped_column(String, primary_key=True)
    event_key:    Mapped[str]      = mapped_column(String, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
