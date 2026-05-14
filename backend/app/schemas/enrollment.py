import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enrollment import EnrollmentStatus


class ProgressSummary(BaseModel):
    total_lessons: int
    completed_lessons: int
    percent: float


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    status: EnrollmentStatus
    enrolled_at: datetime
    completed_at: datetime | None


class EnrollmentWithCourse(EnrollmentResponse):
    course_title: str
    progress_summary: ProgressSummary
