"""add lesson content_text for inline text lessons

Revision ID: 5e3b1f7c9a48
Revises: 4d9a2c5e7b13
Create Date: 2026-06-02

Additive: new nullable column. No existing data is affected; lessons that
previously stored only a content_url keep working. Text lessons can now
carry their body inline, which removes the URL roundtrip and makes them
trivially chunkable for Week 4.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5e3b1f7c9a48"
down_revision: str | None = "4d9a2c5e7b13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lessons",
        sa.Column("content_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lessons", "content_text")
