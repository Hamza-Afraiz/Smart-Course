import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrollment_id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    issued_at: datetime
    certificate_url: str | None = None
    course_title: str | None = None
