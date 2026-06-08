import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.lesson import ContentType


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    order_index: int = Field(ge=0)
    content_type: ContentType | None = None
    # video/pdf may come from EITHER content_url (paste a link) OR storage_key
    # (file uploaded to our object store). text → content_text (inline body).
    content_url: str | None = Field(None, max_length=1000)
    content_text: str | None = None
    storage_key: str | None = Field(None, max_length=1000)
    mime_type: str | None = Field(None, max_length=255)
    file_size: int | None = Field(None, ge=0)
    duration_seconds: int | None = Field(None, ge=0)


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    order_index: int
    content_type: ContentType | None
    content_url: str | None
    content_text: str | None
    storage_key: str | None
    mime_type: str | None
    # Resolved playback URL the browser can hit: a presigned GET when the lesson
    # has a storage_key, else the external content_url. Filled in by the router.
    playback_url: str | None = None
    duration_seconds: int | None
    created_at: datetime
    updated_at: datetime


# ── Upload (presigned PUT) ────────────────────────────────────────────────────

class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=255)  # MIME, e.g. video/mp4


class UploadUrlResponse(BaseModel):
    upload_url: str   # browser PUTs the file bytes here
    storage_key: str  # send this back in LessonCreate.storage_key
