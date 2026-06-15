"""Idempotent dev seed users — run after Alembic migrate."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import UserRole
from app.repositories import user_repo
from app.services.auth_service import _hash_password

logger = logging.getLogger(__name__)


async def seed_dev_users() -> None:
    if not settings.seed_dev_users:
        logger.info("seed_dev_users disabled — skipping")
        return

    async with AsyncSessionLocal() as session:
        async with session.begin():
            for email, password, full_name, role in (
                (
                    settings.dev_admin_email,
                    settings.dev_admin_password,
                    "SmartCourse Admin",
                    UserRole.admin,
                ),
                (
                    settings.dev_instructor_email,
                    settings.dev_instructor_password,
                    "Demo Instructor",
                    UserRole.instructor,
                ),
            ):
                if await user_repo.get_by_email(session, email):
                    logger.info("seed: user already exists — %s", email)
                    continue
                hashed = _hash_password(password)
                await user_repo.create(
                    session,
                    email=email,
                    hashed_password=hashed,
                    full_name=full_name,
                    role=role,
                )
                logger.info("seed: created %s (%s)", email, role.value)


def main() -> None:
    asyncio.run(seed_dev_users())


if __name__ == "__main__":
    main()
