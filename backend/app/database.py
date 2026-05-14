from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    # print generated SQL in development — helps debug query issues
    echo=settings.is_development,
    # max open connections kept in pool
    pool_size=10,
    # extra connections allowed beyond pool_size under burst load
    max_overflow=20,
    # test each connection before using it — handles DB restarts gracefully
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    # do not expire attributes after commit
    # without this, accessing model fields after commit raises DetachedInstanceError
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
