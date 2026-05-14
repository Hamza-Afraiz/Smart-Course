"""Run the course publishing Temporal workflow to completion (tests only)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.temporal.activities import course_publish as cap
from app.temporal.workflows.course_publishing import CoursePublishingWorkflow


async def run_publish_workflow_to_completion(
    engine,
    course_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> None:
    """Blocks until the publish saga finishes — uses an in-process Temporal test server."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    cap.configure_activity_session_factory(factory)
    try:
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="course-publishing",
                workflows=[CoursePublishingWorkflow],
                activities=[
                    cap.validate_course_activity,
                    cap.process_lessons_activity,
                    cap.mark_published_activity,
                    cap.delete_processed_data_activity,
                    cap.revert_to_draft_activity,
                ],
            ):
                await env.client.execute_workflow(
                    CoursePublishingWorkflow.run,
                    args=[str(course_id), str(instructor_id)],
                    id=f"publish-{course_id}",
                    task_queue="course-publishing",
                )
    finally:
        cap.configure_activity_session_factory(None)
