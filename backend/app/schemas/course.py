import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.course import CourseStatus


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    max_students: int | None = Field(None, gt=0)


class CourseUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    max_students: int | None = Field(None, gt=0)
    status: CourseStatus | None = None


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    instructor_id: uuid.UUID
    status: CourseStatus
    max_students: int | None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
