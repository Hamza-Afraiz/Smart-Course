from fastapi import APIRouter

from app.dependencies import InstructorUser
from app.schemas.lesson import UploadUrlRequest, UploadUrlResponse
from app.services import storage_service

router = APIRouter(tags=["Uploads"])


@router.post("", response_model=UploadUrlResponse)
async def create_upload_url(
    payload: UploadUrlRequest,
    _instructor: InstructorUser,
) -> UploadUrlResponse:
    """Hand the browser a presigned URL to PUT a file straight to object
    storage (the bytes never pass through our API). Returns the storage_key
    to send back in LessonCreate.storage_key once the upload finishes.
    """
    key = storage_service.make_key(payload.filename)
    url = storage_service.presign_put(key, payload.content_type)
    return UploadUrlResponse(upload_url=url, storage_key=key)
