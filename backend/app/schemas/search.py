import uuid

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    course_id: uuid.UUID | None = None  # optional — scope to one course
    limit: int = Field(5, ge=1, le=20)


class GlobalSearchRequest(BaseModel):
    """Search across the caller's accessible courses (no course_id — the
    backend derives the scope from the user's enrollments/ownership/role)."""
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(8, ge=1, le=20)


class SearchHit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lesson_id: uuid.UUID
    lesson_title: str
    course_id: uuid.UUID
    course_title: str
    chunk_index: int
    text: str
    similarity: float  # 0.0–1.0; higher = more relevant


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
