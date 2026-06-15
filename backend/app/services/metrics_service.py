"""Compose the admin analytics endpoint responses.

Each method calls one or both stores (Postgres for current state via
metrics_repo, MongoDB for event-log shapes via events_repo) and returns
a Pydantic-validated payload. The router never touches a repo directly.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import CourseStatus
from app.models.user import UserRole
from app.repositories import events_repo, metrics_repo
from app.observability import metrics
from app.schemas.metrics import (
    CompletionMetrics,
    DayBucket,
    EnrollmentsTimeSeries,
    OutboxHealth,
    OverviewMetrics,
    PipelineHealth,
    PopularCourse,
    PopularCourses,
    RecentActivity,
    RecentActivityItem,
)

# Outbox backlog thresholds — tuned for local dev; adjust for prod SLOs.
_DEGRADED_PENDING = 1
_DEGRADED_AGE_SEC = 60.0
_CRITICAL_PENDING = 10
_CRITICAL_AGE_SEC = 300.0


async def overview(db: AsyncSession) -> OverviewMetrics:
    users_by_role = await metrics_repo.count_users_by_role(db)
    courses_by_status = await metrics_repo.count_courses_by_status(db)
    total_enrollments = await metrics_repo.count_enrollments(db)
    avg_per_student = await metrics_repo.avg_courses_per_student(db)
    return OverviewMetrics(
        total_students=users_by_role.get(UserRole.student, 0),
        total_instructors=users_by_role.get(UserRole.instructor, 0),
        total_courses_published=courses_by_status.get(CourseStatus.published, 0),
        total_courses_draft=courses_by_status.get(CourseStatus.draft, 0),
        total_courses_archived=courses_by_status.get(CourseStatus.archived, 0),
        total_enrollments=total_enrollments,
        avg_courses_per_student=avg_per_student,
    )


async def enrollments_time_series(*, days: int) -> EnrollmentsTimeSeries:
    rows = await events_repo.enrollments_per_day(days=days)
    return EnrollmentsTimeSeries(
        series=[DayBucket(date=r["_id"], count=r["count"]) for r in rows]
    )


async def popular_courses(db: AsyncSession, *, limit: int) -> PopularCourses:
    rows = await metrics_repo.list_popular_courses(db, limit=limit)
    return PopularCourses(
        courses=[
            PopularCourse(course_id=cid, title=title, enrollment_count=n)
            for cid, title, n in rows
        ]
    )


async def completion(db: AsyncSession) -> CompletionMetrics:
    stats = await metrics_repo.enrollment_completion_stats(db)
    return CompletionMetrics(
        completion_rate=round(stats["rate"], 4),
        avg_completion_seconds=stats["avg_seconds"],
        completed_enrollments=stats["completed"],
        active_enrollments=stats["active"],
    )


def _pipeline_status(
    pending_count: int, oldest_pending_seconds: float | None
) -> tuple[str, list[str]]:
    hints: list[str] = []
    if pending_count == 0:
        return "healthy", ["Outbox is empty — relay is keeping up with producers."]

    age = oldest_pending_seconds or 0.0
    hints.append(
        f"{pending_count} event(s) waiting in the outbox "
        f"(oldest {age:.0f}s). Check relay + Kafka if this persists."
    )
    if pending_count >= _CRITICAL_PENDING or age >= _CRITICAL_AGE_SEC:
        hints.append("Likely relay or Kafka outage — events are not reaching consumers.")
        return "critical", hints
    if pending_count >= _DEGRADED_PENDING or age >= _DEGRADED_AGE_SEC:
        hints.append("Transient backlog or slow relay — monitor Grafana events-pipeline dashboard.")
        return "degraded", hints
    return "healthy", hints


def _consumer_errors_total() -> int:
    """Sum Kafka consumer samples recorded with outcome=error."""
    total = 0.0
    for label_values, metric in metrics.events_consumed_total._metrics.items():
        if len(label_values) >= 3 and label_values[2] == "error":
            total += metric._value.get()
    return int(total)


async def pipeline_health(db: AsyncSession) -> PipelineHealth:
    stats = await metrics_repo.outbox_health_stats(db)
    pending_count = int(stats["pending_count"])
    oldest = stats["oldest_pending_seconds"]
    oldest_f = float(oldest) if oldest is not None else None

    status, hints = _pipeline_status(pending_count, oldest_f)
    metrics.outbox_pending.set(pending_count)

    return PipelineHealth(
        status=status,
        outbox=OutboxHealth(
            pending_count=pending_count,
            oldest_pending_seconds=oldest_f,
            pending_by_type=dict(stats["pending_by_type"]),
        ),
        consumer_errors_total=_consumer_errors_total(),
        hints=hints,
    )


async def recent_activity(*, limit: int) -> RecentActivity:
    docs = await events_repo.recent_activity(limit=limit)
    return RecentActivity(
        items=[
            RecentActivityItem(
                event_type=d["event_type"],
                event_key=d["event_key"],
                archived_at=d["archived_at"],
                payload=d["payload"],
            )
            for d in docs
        ]
    )
