import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from temporalio.client import WorkflowFailureError
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.testing import WorkflowEnvironment

from app.database import get_db
from app.main import app
from app.models import Base
from app.temporal.workflows.course_publishing import CoursePublishingWorkflow
from tests.conftest import TEST_DATABASE_URL, _register_and_login
from tests.publish_helpers import run_publish_workflow_to_completion


@pytest_asyncio.fixture
async def tp_engine():
    """Isolated engine for Temporal workflow tests (own schema)."""
    eng = create_async_engine(TEST_DATABASE_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def tp_client(tp_engine):
    SessionLocal = async_sessionmaker(tp_engine, class_=AsyncSession, expire_on_commit=False)

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


@pytest_asyncio.fixture
async def tp_instructor_headers(tp_client):
    return await _register_and_login(
        tp_client, "twf-instructor@test.com", "secret123", "instructor"
    )


async def _draft_course_with_lessons(tp_client, headers):
    r = await tp_client.post(
        "/api/v1/courses", headers=headers, json={"title": "Temporal WF"}
    )
    assert r.status_code == 201, r.text
    course = r.json()
    mid = (
        await tp_client.post(
            f"/api/v1/courses/{course['id']}/modules",
            headers=headers,
            json={"title": "m", "order_index": 0},
        )
    ).json()["id"]
    for i in range(2):
        lr = await tp_client.post(
            f"/api/v1/courses/{course['id']}/modules/{mid}/lessons",
            headers=headers,
            json={"title": f"l{i}", "order_index": i},
        )
        assert lr.status_code == 201, lr.text
    return course


@pytest.mark.asyncio
async def test_publish_workflow_happy_path(tp_client, tp_instructor_headers, tp_engine):
    course = await _draft_course_with_lessons(tp_client, tp_instructor_headers)
    cid = uuid.UUID(course["id"])
    iid = uuid.UUID(course["instructor_id"])
    await run_publish_workflow_to_completion(tp_engine, cid, iid)
    got = await tp_client.get(
        f"/api/v1/courses/{course['id']}", headers=tp_instructor_headers
    )
    assert got.json()["status"] == "published"
    assert got.json().get("processed_at") is not None


@pytest.mark.asyncio
async def test_publish_process_step_failure_no_compensation(
    tp_client, tp_instructor_headers, tp_engine
):
    course = await _draft_course_with_lessons(tp_client, tp_instructor_headers)
    cid = uuid.UUID(course["id"])
    iid = uuid.UUID(course["instructor_id"])
    os.environ["TEST_PUBLISH_FAIL_STEP"] = "process"
    try:
        with pytest.raises(WorkflowFailureError):
            await run_publish_workflow_to_completion(tp_engine, cid, iid)
    finally:
        del os.environ["TEST_PUBLISH_FAIL_STEP"]
    got = await tp_client.get(
        f"/api/v1/courses/{course['id']}", headers=tp_instructor_headers
    )
    assert got.json()["status"] == "draft"
    assert got.json().get("processed_at") is None


@pytest.mark.asyncio
async def test_publish_mark_step_failure_runs_compensation(
    tp_client, tp_instructor_headers, tp_engine
):
    course = await _draft_course_with_lessons(tp_client, tp_instructor_headers)
    cid = uuid.UUID(course["id"])
    iid = uuid.UUID(course["instructor_id"])
    os.environ["TEST_PUBLISH_FAIL_STEP"] = "mark"
    try:
        with pytest.raises(WorkflowFailureError):
            await run_publish_workflow_to_completion(tp_engine, cid, iid)
    finally:
        del os.environ["TEST_PUBLISH_FAIL_STEP"]
    got = await tp_client.get(
        f"/api/v1/courses/{course['id']}", headers=tp_instructor_headers
    )
    assert got.json()["status"] == "draft"
    assert got.json().get("processed_at") is None


@pytest.mark.asyncio
async def test_duplicate_workflow_id_raises():
    """Second start with same workflow id fails before any worker picks up the run."""
    cid = uuid.uuid4()
    iid = uuid.uuid4()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        wid = f"publish-{cid}"
        await env.client.start_workflow(
            CoursePublishingWorkflow.run,
            args=[str(cid), str(iid)],
            id=wid,
            task_queue="course-publishing",
        )
        with pytest.raises(WorkflowAlreadyStartedError):
            await env.client.start_workflow(
                CoursePublishingWorkflow.run,
                args=[str(cid), str(iid)],
                id=wid,
                task_queue="course-publishing",
            )
