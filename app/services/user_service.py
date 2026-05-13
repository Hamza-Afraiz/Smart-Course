import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import UserNotFoundError
from app.models.user import User
from app.repositories import user_repo
from app.services.auth_service import _hash_password


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError(f"User {user_id} not found")
    return user


async def update_me(
    db: AsyncSession,
    *,
    current_user: User,
    full_name: str | None,
    password: str | None,
) -> User:
    if full_name is not None:
        current_user.full_name = full_name

    if password is not None:
        loop = asyncio.get_event_loop()
        current_user.hashed_password = await loop.run_in_executor(None, _hash_password, password)

    await db.flush()
    return current_user
