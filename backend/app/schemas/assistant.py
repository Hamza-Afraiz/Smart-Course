import uuid
from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    course_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)


class GenerateRequest(BaseModel):
    """Instructor-only: generate a summary or quiz from indexed lesson content."""

    course_id: uuid.UUID
    kind: Literal["summary", "quiz"]
    lesson_id: uuid.UUID | None = None  # None = whole-course scope
