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
from app.schemas.metrics import (
    CompletionMetrics,
    DayBucket,
    EnrollmentsTimeSeries,
    OverviewMetrics,
    PopularCourse,
    PopularCourses,
    RecentActivity,
    RecentActivityItem,
)


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
