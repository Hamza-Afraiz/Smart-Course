import uuid

from pydantic import BaseModel, ConfigDict

from app.models.course import CourseStatus


class CourseRecommendation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    instructor_id: uuid.UUID
    status: CourseStatus
    popularity: int
