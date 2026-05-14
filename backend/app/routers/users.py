import uuid

from fastapi import APIRouter, HTTPException, status

from app.dependencies import AdminUser, CurrentUser, DBSession
from app.exceptions import UserNotFoundError
from app.schemas.user import UserResponse, UserUpdateRequest
from app.services import user_service

router = APIRouter(tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(payload: UserUpdateRequest, current_user: CurrentUser, db: DBSession) -> UserResponse:
    user = await user_service.update_me(
        db,
        current_user=current_user,
        full_name=payload.full_name,
        password=payload.password,
    )
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, _admin: AdminUser, db: DBSession) -> UserResponse:
    try:
        return await user_service.get_by_id(db, user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
