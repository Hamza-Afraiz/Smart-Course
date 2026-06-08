"""add lesson storage (uploads) + extraction cache columns

Revision ID: 7a1c5d9e2f04
Revises: 6f4e2a8b1d63
Create Date: 2026-06-03

Additive — all nullable. Existing lessons (URL-based or text) keep working.

- storage_key / mime_type / file_size: set when an instructor UPLOADS a file
  to our object store (MinIO in dev, R2/S3 in prod) instead of pasting a URL.
  When present, storage_key is the effective source.
- cached_text / cached_text_source: memoised transcript (video) or extracted
  text (pdf) so re-publishing an unchanged lesson skips Whisper / pypdf.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7a1c5d9e2f04"
down_revision: str | None = "6f4e2a8b1d63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("storage_key", sa.String(length=1000), nullable=True))
    op.add_column("lessons", sa.Column("mime_type", sa.String(length=255), nullable=True))
    op.add_column("lessons", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("lessons", sa.Column("cached_text", sa.Text(), nullable=True))
    op.add_column("lessons", sa.Column("cached_text_source", sa.String(length=1100), nullable=True))


def downgrade() -> None:
    op.drop_column("lessons", "cached_text_source")
    op.drop_column("lessons", "cached_text")
    op.drop_column("lessons", "file_size")
    op.drop_column("lessons", "mime_type")
    op.drop_column("lessons", "storage_key")
