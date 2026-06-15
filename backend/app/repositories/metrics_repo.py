"""Postgres aggregations for the admin metrics.

Counts of *current* state — users by role, courses by status, enrollments
and their completion. These are SQL problems (aggregate counts, GROUP BY,
AVG over an interval), so Postgres wins. Time-series and event-log
aggregations live in `events_repo` against MongoDB instead.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Numeric, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone

from app.models.course import Course, CourseStatus
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.outbox import OutboxEvent
from app.models.user import User, UserRole


async def count_users_by_role(db: AsyncSession) -> dict[UserRole, int]:
    """One row per role with its user count — single round trip."""
    result = await db.execute(
        select(User.role, func.count()).group_by(User.role)
    )
    return {role: int(count) for role, count in result.all()}


async def count_courses_by_status(db: AsyncSession) -> dict[CourseStatus, int]:
    result = await db.execute(
        select(Course.status, func.count()).group_by(Course.status)
    )
    return {status: int(count) for status, count in result.all()}


async def count_enrollments(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(Enrollment))
    return int(result.scalar_one())


async def avg_courses_per_student(db: AsyncSession) -> float:
    """Total enrollments / total students, with zero-student guard."""
    result = await db.execute(
        select(
            func.count(Enrollment.id).label("enrollments"),
            func.count(func.distinct(User.id)).label("students"),
        )
        .select_from(User)
        .outerjoin(Enrollment, Enrollment.student_id == User.id)
        .where(User.role == UserRole.student)
    )
    row = result.one()
    if not row.students:
        return 0.0
    return round(float(row.enrollments) / float(row.students), 2)


async def enrollment_completion_stats(db: AsyncSession) -> dict[str, float | int | None]:
    """Completion rate + average completion duration in one round trip."""
    result = await db.execute(
        select(
            func.count(
                case((Enrollment.status == EnrollmentStatus.completed, 1))
            ).label("completed"),
            func.count(
                case((Enrollment.status == EnrollmentStatus.active, 1))
            ).label("active"),
            # AVG(completed_at - enrolled_at) — returns a Postgres `interval`
            cast(
                func.avg(
                    func.extract(
                        "epoch", Enrollment.completed_at - Enrollment.enrolled_at
                    )
                ),
                Numeric,
            ).label("avg_seconds"),
        ).where(Enrollment.status != EnrollmentStatus.dropped)
    )
    row = result.one()
    completed = int(row.completed)
    active = int(row.active)
    total = completed + active
    return {
        "completed": completed,
        "active": active,
        "rate": (completed / total) if total else 0.0,
        "avg_seconds": float(row.avg_seconds) if row.avg_seconds is not None else None,
    }


async def list_popular_courses(
    db: AsyncSession, *, limit: int
) -> list[tuple[uuid.UUID, str, int]]:
    """Courses with the most enrollments, joined to their title."""
    result = await db.execute(
        select(
            Course.id, Course.title, func.count(Enrollment.id).label("enrollment_count")
        )
        .join(Enrollment, Enrollment.course_id == Course.id)
        .group_by(Course.id)
        .order_by(func.count(Enrollment.id).desc())
        .limit(limit)
    )
    return [(cid, title, int(n)) for cid, title, n in result.all()]


async def outbox_health_stats(db: AsyncSession) -> dict[str, int | float | None | dict[str, int]]:
    """Unsent outbox rows — the primary 'failed / stuck pipeline' signal for admins."""
    pending_result = await db.execute(
        select(func.count())
        .select_from(OutboxEvent)
        .where(OutboxEvent.sent_at.is_(None))
    )
    pending_count = int(pending_result.scalar_one())

    oldest_pending_seconds: float | None = None
    pending_by_type: dict[str, int] = {}
    if pending_count:
        oldest_result = await db.execute(
            select(func.min(OutboxEvent.created_at)).where(OutboxEvent.sent_at.is_(None))
        )
        oldest_dt = oldest_result.scalar_one()
        if oldest_dt is not None:
            oldest_pending_seconds = (
                datetime.now(timezone.utc) - oldest_dt
            ).total_seconds()

        type_result = await db.execute(
            select(OutboxEvent.event_type, func.count())
            .where(OutboxEvent.sent_at.is_(None))
            .group_by(OutboxEvent.event_type)
        )
        pending_by_type = {event_type: int(n) for event_type, n in type_result.all()}

    return {
        "pending_count": pending_count,
        "oldest_pending_seconds": oldest_pending_seconds,
        "pending_by_type": pending_by_type,
    }
