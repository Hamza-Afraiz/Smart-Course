"""add outbox traceparent for cross-service tracing

Revision ID: 8b2c4d6e1f90
Revises: 7a1c5d9e2f04
Create Date: 2026-06-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8b2c4d6e1f90"
down_revision: Union[str, None] = "7a1c5d9e2f04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("outbox", sa.Column("traceparent", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("outbox", "traceparent")
