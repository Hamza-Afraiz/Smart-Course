import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EnrollmentStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    dropped = "dropped"


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        # DB-level guard against duplicate enrollments under concurrent requests
        UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),
        Index("idx_enrollments_student_id", "student_id"),
        Index("idx_enrollments_course_id", "course_id"),
        # common query: "get active enrollments for student"
        Index("idx_enrollments_student_status", "student_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(EnrollmentStatus, name="enrollmentstatus"),
        default=EnrollmentStatus.active,
        nullable=False,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # set when status transitions to completed — drives certificate issuance
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped["User"] = relationship(
        "User", back_populates="enrollments", foreign_keys=[student_id]
    )
    course: Mapped["Course"] = relationship("Course", back_populates="enrollments")
    progress_records: Mapped[list["Progress"]] = relationship(
        "Progress", back_populates="enrollment", cascade="all, delete-orphan"
    )
    certificate: Mapped["Certificate | None"] = relationship(
        "Certificate", back_populates="enrollment", uselist=False
    )
