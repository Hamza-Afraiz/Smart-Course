import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrollment_id: uuid.UUID
    lesson_id: uuid.UUID
    completed_at: datetime
