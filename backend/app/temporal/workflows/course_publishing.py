"""Course publishing saga — Temporal workflow (deterministic orchestration only)."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.exceptions import ActivityError


@workflow.defn
class CoursePublishingWorkflow:
    @workflow.run
    async def run(self, course_id: str, instructor_id: str) -> None:
        info = workflow.info()
        run_id = info.run_id
        key2 = f"publish-{course_id}-{run_id}-step-2"
        key3 = f"publish-{course_id}-{run_id}-step-3"

        step2_complete = False
        try:
            await workflow.execute_activity(
                "validate_course_activity",
                args=[course_id, instructor_id],
                start_to_close_timeout=timedelta(seconds=120),
            )
            await workflow.execute_activity(
                "process_lessons_activity",
                args=[course_id, key2],
                start_to_close_timeout=timedelta(seconds=120),
            )
            step2_complete = True
            await workflow.execute_activity(
                "mark_published_activity",
                args=[course_id, key3],
                start_to_close_timeout=timedelta(seconds=120),
            )
        except ActivityError:
            if step2_complete:
                await workflow.execute_activity(
                    "delete_processed_data_activity",
                    args=[course_id],
                    start_to_close_timeout=timedelta(seconds=120),
                )
            raise

        # Step 4: announce. Outside the saga's try/except — the course IS
        # already published; if this Kafka publish fails permanently, the
        # workflow ends in failed state but the DB stays consistent (course
        # status = published; no rollback runs). Temporal retries transient
        # failures automatically; consumer-side dedupe absorbs duplicates.
        await workflow.execute_activity(
            "emit_course_published_activity",
            args=[course_id, run_id],
            start_to_close_timeout=timedelta(seconds=30),
        )
