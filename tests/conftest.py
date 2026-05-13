import psycopg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models import Base

TEST_DB_NAME = "smartcourse_test"
TEST_DATABASE_URL = (
    f"postgresql+psycopg://smartcourse:smartcourse@localhost:5432/{TEST_DB_NAME}"
)
ADMIN_DATABASE_URL = "postgresql://smartcourse:smartcourse@localhost:5432/postgres"


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_database():
    """Create smartcourse_test database once per session if it doesn't exist."""
    conn = psycopg.connect(ADMIN_DATABASE_URL, autocommit=True)
    try:
        cur = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (TEST_DB_NAME,)
        )
        if not cur.fetchone():
            conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        conn.close()


@pytest_asyncio.fixture
async def engine():
    """Fresh schema per test — drop_all then create_all keeps tests isolated."""
    eng = create_async_engine(TEST_DATABASE_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine):
    """HTTP client wired to the test database via dependency override."""
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _register_and_login(
    client: AsyncClient, email: str, password: str, role: str
) -> dict[str, str]:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "role": role},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def student_headers(client) -> dict[str, str]:
    return await _register_and_login(client, "student@test.com", "secret123", "student")


@pytest_asyncio.fixture
async def instructor_headers(client) -> dict[str, str]:
    return await _register_and_login(client, "instructor@test.com", "secret123", "instructor")


@pytest_asyncio.fixture
async def other_instructor_headers(client) -> dict[str, str]:
    """A second instructor — used to verify ownership rules."""
    return await _register_and_login(client, "other@test.com", "secret123", "instructor")
