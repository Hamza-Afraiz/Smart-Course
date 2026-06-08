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
    from app.observability.metrics_server import start_metrics_server
    from app.database import engine
    from app.services import embedding_service
    configure_json_logging(service_name="temporal-worker")
    configure_tracing(service_name="temporal-worker")
    instrument_sqlalchemy(engine)
    start_metrics_server()  # Prometheus → up{job="temporal-worker"}
    cap.configure_activity_session_factory(AsyncSessionLocal)

    # Pre-load the embedding model so the first publish doesn't pay the
    # ~80MB download + load cost inside the activity (would overflow its timeout).
    logger.info("warming embedding model...")
    embedding_service.warm_up()
    logger.info("embedding model ready")

    # Whisper for video transcription — tiny model, ~39MB on disk.
    # Loaded lazily on first publish today; eager-loading here avoids the
    # first-publish-pays-for-load cost like we did for embeddings.
    try:
        from app.services import extraction_service
        extraction_service.warm_whisper()
    except Exception as e:
        # Whisper is optional — if download/load fails we'll just skip video
        # transcription. The publish workflow doesn't fail because of it.
        logger.warning("whisper warm-up skipped: %s", e)
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
