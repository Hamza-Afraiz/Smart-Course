import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.lesson import ContentType


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    order_index: int = Field(ge=0)
    content_type: ContentType | None = None
    content_url: str | None = Field(None, max_length=1000)
    duration_seconds: int | None = Field(None, ge=0)


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    order_index: int
    content_type: ContentType | None
    content_url: str | None
    duration_seconds: int | None
    created_at: datetime
    updated_at: datetime
