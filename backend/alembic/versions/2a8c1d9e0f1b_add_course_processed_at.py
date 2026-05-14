"""add course processed_at for publish pipeline

Revision ID: 2a8c1d9e0f1b
Revises: 1ff633244782
Create Date: 2026-05-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2a8c1d9e0f1b"
down_revision: str | None = "1ff633244782"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("courses", "processed_at")
