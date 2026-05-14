import psycopg
import pytest
import pytest_asyncio
import uuid
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


@pytest_asyncio.fixture
async def make_published_course(client, instructor_headers, engine):
    """Create a draft course with one module + two lessons, run publish workflow.

    The returned course dict includes test-only keys ``_module_id`` and
    ``_lesson_ids`` so tests can reference lessons without a list-lessons API.
    """
    from tests.publish_helpers import run_publish_workflow_to_completion

    async def _factory(*, title: str = "Course", max_students: int | None = None):
        payload: dict = {"title": title}
        if max_students is not None:
            payload["max_students"] = max_students
        resp = await client.post(
            "/api/v1/courses", headers=instructor_headers, json=payload
        )
        assert resp.status_code == 201, resp.text
        course = resp.json()
        mod = (
            await client.post(
                f"/api/v1/courses/{course['id']}/modules",
                headers=instructor_headers,
                json={"title": "m0", "order_index": 0},
            )
        ).json()
        assert mod.get("id")
        les1 = await client.post(
            f"/api/v1/courses/{course['id']}/modules/{mod['id']}/lessons",
            headers=instructor_headers,
            json={"title": "l0", "order_index": 0},
        )
        assert les1.status_code == 201, les1.text
        les2 = await client.post(
            f"/api/v1/courses/{course['id']}/modules/{mod['id']}/lessons",
            headers=instructor_headers,
            json={"title": "l1", "order_index": 1},
        )
        assert les2.status_code == 201, les2.text
        await run_publish_workflow_to_completion(
            engine,
            uuid.UUID(course["id"]),
            uuid.UUID(course["instructor_id"]),
        )
        got = await client.get(
            f"/api/v1/courses/{course['id']}", headers=instructor_headers
        )
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["status"] == "published"
        body["_module_id"] = mod["id"]
        body["_lesson_ids"] = [les1.json()["id"], les2.json()["id"]]
        return body

    return _factory
