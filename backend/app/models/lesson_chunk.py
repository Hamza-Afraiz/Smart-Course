from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

EMBEDDING_DIM = 384


class LessonChunk(Base):
    """One chunk of a lesson's source text + its embedding.

    Produced by the Week 4 chunking + embedding pipeline (replaces the
    `process_lessons_activity` stub). The `embedding` is a 384-dim vector
    from sentence-transformers' all-MiniLM-L6-v2; retrieval uses pgvector's
    `<=>` cosine-distance operator with an HNSW index.

    `course_id` is denormalised so retrieval can filter without joining
    through lessons → modules → courses on every query.
    """

    __tablename__ = "lesson_chunks"
    __table_args__ = (
        UniqueConstraint(
            "lesson_id", "chunk_index", name="uq_lesson_chunks_lesson_order"
        ),
        Index("idx_lesson_chunks_course", "course_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lesson: Mapped["Lesson"] = relationship("Lesson")  # type: ignore[name-defined]
