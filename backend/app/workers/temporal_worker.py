"""Run after Temporal server is up: python -m app.workers.temporal_worker"""

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.config import settings
from app.database import AsyncSessionLocal
from app.temporal.activities import course_publish as cap
from app.temporal.workflows.course_publishing import CoursePublishingWorkflow

logger = logging.getLogger(__name__)


async def _run() -> None:
    from app.observability.logging import configure_json_logging
    from app.observability.tracing import configure_tracing, instrument_sqlalchemy
    from app.database import engine
    configure_json_logging(service_name="temporal-worker")
    configure_tracing(service_name="temporal-worker")
    instrument_sqlalchemy(engine)
    cap.configure_activity_session_factory(AsyncSessionLocal)
    client = await Client.connect(settings.temporal_host, namespace="default")
    worker = Worker(
        client,
        task_queue="course-publishing",
        workflows=[CoursePublishingWorkflow],
        activities=[
            cap.validate_course_activity,
            cap.process_lessons_activity,
            cap.mark_published_activity,
            cap.emit_course_published_activity,
            cap.delete_processed_data_activity,
            cap.revert_to_draft_activity,
        ],
    )
    logger.info(
        "Temporal worker polling task_queue=course-publishing — Temporal at %s",
        settings.temporal_host,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(_run())
