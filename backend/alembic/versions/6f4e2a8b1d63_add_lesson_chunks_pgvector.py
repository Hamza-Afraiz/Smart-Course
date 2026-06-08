"""add lesson_chunks table + enable pgvector extension

Revision ID: 6f4e2a8b1d63
Revises: 5e3b1f7c9a48
Create Date: 2026-06-02

Foundation for Week 4 RAG retrieval. The `vector` extension comes from the
pgvector/pgvector:pg15 Docker image — already compiled into Postgres. We
just turn it on.

The lesson_chunks table is the universal store for chunks of every lesson,
regardless of content_type (text/video/pdf). One row per (lesson, chunk_index).
A 384-dim vector column matches the dimensions of sentence-transformers'
all-MiniLM-L6-v2 model. If we ever swap embedder, the dimension is the only
schema change needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "6f4e2a8b1d63"
down_revision: str | None = "5e3b1f7c9a48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


def upgrade() -> None:
    # Enable the extension — idempotent. Requires the pgvector/pgvector image.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "lesson_chunks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "lesson_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalised — saved on every chunk so retrieval can filter by course
        # without joining through lessons → modules → courses on every query.
        sa.Column(
            "course_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lesson_id", "chunk_index", name="uq_lesson_chunks_lesson_order"
        ),
    )

    # Filter-by-course is the hot path of retrieval queries
    op.create_index(
        "idx_lesson_chunks_course", "lesson_chunks", ["course_id"]
    )

    # HNSW vector index — fast ANN search over the embeddings.
    # `vector_cosine_ops` matches what we'll query with (`<=>` = cosine distance).
    op.execute(
        "CREATE INDEX idx_lesson_chunks_embedding "
        "ON lesson_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("idx_lesson_chunks_embedding", table_name="lesson_chunks")
    op.drop_index("idx_lesson_chunks_course", table_name="lesson_chunks")
    op.drop_table("lesson_chunks")
    # Leave the extension installed — it might be used elsewhere
