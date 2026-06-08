import uuid

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    course_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)
