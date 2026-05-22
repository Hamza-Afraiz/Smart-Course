from fastapi import APIRouter, Query

from app.dependencies import AdminUser, DBSession
from app.schemas.metrics import (
    CompletionMetrics,
    EnrollmentsTimeSeries,
    OverviewMetrics,
    PopularCourses,
    RecentActivity,
)
from app.services import metrics_service

router = APIRouter(tags=["Admin / Metrics"])


@router.get("/overview", response_model=OverviewMetrics)
async def get_overview(_admin: AdminUser, db: DBSession) -> OverviewMetrics:
    """Top-line platform counts — students, instructors, courses, enrollments."""
    return await metrics_service.overview(db)


@router.get("/enrollments-over-time", response_model=EnrollmentsTimeSeries)
async def get_enrollments_over_time(
    _admin: AdminUser,
    days: int = Query(30, ge=1, le=365),
) -> EnrollmentsTimeSeries:
    """Daily new-enrollment series from the Mongo event log."""
    return await metrics_service.enrollments_time_series(days=days)


@router.get("/popular-courses", response_model=PopularCourses)
async def get_popular_courses(
    _admin: AdminUser,
    db: DBSession,
    limit: int = Query(10, ge=1, le=50),
) -> PopularCourses:
    """Courses with the most enrollments."""
    return await metrics_service.popular_courses(db, limit=limit)


@router.get("/completion", response_model=CompletionMetrics)
async def get_completion(_admin: AdminUser, db: DBSession) -> CompletionMetrics:
    """Course completion rate + average time-to-complete (excludes dropped)."""
    return await metrics_service.completion(db)


@router.get("/recent-activity", response_model=RecentActivity)
async def get_recent_activity(
    _admin: AdminUser,
    limit: int = Query(20, ge=1, le=100),
) -> RecentActivity:
    """Latest events of any type, from the Mongo event log."""
    return await metrics_service.recent_activity(limit=limit)
