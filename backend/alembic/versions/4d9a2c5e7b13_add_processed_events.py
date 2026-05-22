"""add processed_events table for consumer-side dedupe

Revision ID: 4d9a2c5e7b13
Revises: 3c8f1b4a9d52
Create Date: 2026-05-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d9a2c5e7b13"
down_revision: str | None = "3c8f1b4a9d52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("consumer", sa.String(), nullable=False),
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("consumer", "event_key"),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
