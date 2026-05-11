from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ── Core Auth Dependencies ────────────────────────────────────────────────────

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode JWT, validate, and return the User. Raises 401 on any failure."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise invalid
    except JWTError:
        raise invalid

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise invalid
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Raises 403 if the account has been deactivated."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    return current_user


def require_role(*roles: UserRole):
    """
    Dependency factory for role-based access control.

    Usage:
        Depends(require_role(UserRole.instructor, UserRole.admin))
    """
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


# ── Type Aliases ──────────────────────────────────────────────────────────────
# Import these in routers for clean, readable signatures.
#
# Instead of:
#   async def create_course(
#       db: Annotated[AsyncSession, Depends(get_db)],
#       current_user: Annotated[User, Depends(get_current_active_user)],
#   )
#
# Write:
#   async def create_course(db: DBSession, current_user: CurrentUser)

DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
InstructorUser = Annotated[User, Depends(require_role(UserRole.instructor, UserRole.admin))]
AdminUser = Annotated[User, Depends(require_role(UserRole.admin))]
