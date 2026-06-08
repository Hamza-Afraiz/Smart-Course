import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ContentType(str, enum.Enum):
    video = "video"
    text = "text"
    pdf = "pdf"


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        Index("idx_lessons_module_order", "module_id", "order_index"),
        UniqueConstraint("module_id", "order_index", name="uq_lesson_module_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[ContentType | None] = mapped_column(
        SAEnum(ContentType, name="contenttype")
    )
    # ── Content source (video/pdf can come from EITHER of these) ──────────────
    # External URL — instructor pasted a YouTube / CDN link.
    content_url: Mapped[str | None] = mapped_column(String(1000))
    # Object-store key — instructor uploaded a file to our MinIO/S3 bucket.
    # When set, it takes precedence over content_url for both extraction and
    # playback (see lesson_service.effective_source).
    storage_key: Mapped[str | None] = mapped_column(String(1000))
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    # Inline body — used for `text` content. Stored directly so the Week 4
    # chunking pipeline can split it without a fetch+parse roundtrip.
    content_text: Mapped[str | None] = mapped_column(Text)

    # ── Extraction cache (video transcript / pdf text) ───────────────────────
    # Avoids re-running Whisper / pypdf on every re-publish. Invalidated when
    # `cached_text_source` no longer matches the lesson's effective source.
    cached_text: Mapped[str | None] = mapped_column(Text)
    cached_text_source: Mapped[str | None] = mapped_column(String(1100))

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # only meaningful for video content_type, nullable for text/pdf
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    module: Mapped["Module"] = relationship("Module", back_populates="lessons")
    progress_records: Mapped[list["Progress"]] = relationship(
        "Progress", back_populates="lesson"
    )
