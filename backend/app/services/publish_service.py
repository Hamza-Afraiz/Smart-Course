import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from app.exceptions import (
    ForbiddenError,
    PublishWorkflowInProgressError,
    TemporalUnavailableError,
    WorkflowNotFoundError,
)
from app.models.course import CourseStatus
from app.models.user import User
from app.services import course_service
from app.temporal.workflows.course_publishing import CoursePublishingWorkflow

logger = logging.getLogger(__name__)

TASK_QUEUE = "course-publishing"


def workflow_id_for_course(course_id: uuid.UUID) -> str:
    return f"publish-{course_id}"


async def start_publish_workflow(
    client: Client | None,
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    actor: User,
) -> str:
    if client is None:
        raise TemporalUnavailableError(
            "Temporal is not available — start the Temporal server and worker "
            "(see README)"
        )
    course = await course_service.get_for_modify(db, course_id, actor)
    if course.status != CourseStatus.draft:
        raise ForbiddenError(
            "Only a draft course can be published (or it is already published/archived)"
        )
    wf_id = workflow_id_for_course(course_id)
    try:
        await client.start_workflow(
            CoursePublishingWorkflow.run,
            args=[str(course_id), str(course.instructor_id)],
            id=wf_id,
            task_queue=TASK_QUEUE,
        )
    except WorkflowAlreadyStartedError:
        logger.info("Duplicate publish workflow: %s", wf_id)
        raise PublishWorkflowInProgressError(
            "A publish workflow is already running for this course"
        ) from None
    return wf_id


async def describe_publish_workflow(client: Client | None, workflow_id: str) -> str:
    if client is None:
        raise TemporalUnavailableError(
            "Temporal is not available — start the Temporal server and worker "
            "(see README)"
        )
    handle = client.get_workflow_handle(workflow_id)
    try:
        desc = await handle.describe()
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            raise WorkflowNotFoundError("No workflow found for this id") from e
        raise
    return desc.status.name
