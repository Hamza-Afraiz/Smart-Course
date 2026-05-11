import asyncio
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import EmailAlreadyExistsError, InvalidCredentialsError
from app.models.user import User, UserRole
from app.repositories import user_repo


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_access_token(user_id: str, role: UserRole) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "role": role.value, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


async def register(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None,
    role: UserRole,
) -> User:
    existing = await user_repo.get_by_email(db, email)
    if existing:
        raise EmailAlreadyExistsError(email)

    # bcrypt is CPU-bound — must not block the event loop
    loop = asyncio.get_event_loop()
    hashed = await loop.run_in_executor(None, _hash_password, password)

    return await user_repo.create(
        db, email=email, hashed_password=hashed, full_name=full_name, role=role
    )


async def login(db: AsyncSession, *, email: str, password: str) -> str:
    user = await user_repo.get_by_email(db, email)

    # always run verify even when user not found — prevents timing-based user enumeration
    candidate_hash = user.hashed_password if user else "$2b$12$79e8AedYs4TJ64nzg1Gri.qUeRZy1s27hA12eIS5.l3LNduwWTvgq"
    loop = asyncio.get_event_loop()
    valid = await loop.run_in_executor(None, _verify_password, password, candidate_hash)

    if not user or not valid:
        raise InvalidCredentialsError()

    return _create_access_token(str(user.id), user.role)
