import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CourseStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        Index("idx_courses_instructor_id", "instructor_id"),
        Index("idx_courses_status", "status"),
        # GIN index for full-text search on title + description
        Index(
            "idx_courses_search",
            text("to_tsvector('english', title || ' ' || coalesce(description, ''))"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[CourseStatus] = mapped_column(
        SAEnum(CourseStatus, name="coursestatus"),
        default=CourseStatus.draft,
        nullable=False,
    )
    # enrollment cap from PRD — null means unlimited
    max_students: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # set by Temporal publish workflow step 2 — cleared by compensation
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    instructor: Mapped["User"] = relationship("User", back_populates="courses")
    modules: Mapped[list["Module"]] = relationship(
        "Module", back_populates="course", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        "Enrollment", back_populates="course"
    )
    certificates: Mapped[list["Certificate"]] = relationship(
        "Certificate", back_populates="course"
    )


# Self-referential M2M: a course requires N other courses to be completed first.
# Composite PK forbids duplicate edges; the CHECK forbids a self-loop at the DB
# level (the service also rejects it, but defense in depth). No ORM relationship
# is declared on Course — reads go through explicit repo queries so we never
# trip an async lazy-load and can express the recursive cycle check in SQL.
course_prerequisites = Table(
    "course_prerequisites",
    Base.metadata,
    Column(
        "course_id",
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "prerequisite_id",
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    CheckConstraint("course_id <> prerequisite_id", name="ck_course_prereq_no_self"),
    Index("idx_course_prereq_prerequisite", "prerequisite_id"),
)
