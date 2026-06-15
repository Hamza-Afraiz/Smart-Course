import uuid

from pydantic import BaseModel, ConfigDict

from app.models.course import CourseStatus


class PrerequisiteAdd(BaseModel):
    prerequisite_id: uuid.UUID


class PrerequisiteCourse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: CourseStatus
