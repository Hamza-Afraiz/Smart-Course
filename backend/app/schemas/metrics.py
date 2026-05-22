"""Response schemas for the admin analytics endpoints.

These cover the 9 dashboard metrics defined in PRD §5. The actual data
sources are split: counts of current state come from Postgres, time-series
and event-log queries come from MongoDB's `events` collection. The service
layer hides which store each value came from — the routes return one
coherent payload.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OverviewMetrics(BaseModel):
    """The top-line "platform at a glance" numbers — current state."""

    total_students: int
    total_instructors: int
    total_courses_published: int
    total_courses_draft: int
    total_courses_archived: int
    total_enrollments: int
    avg_courses_per_student: float


class DayBucket(BaseModel):
    date: str   # YYYY-MM-DD
    count: int


class EnrollmentsTimeSeries(BaseModel):
    """`user.enrolled` events grouped by day — sourced from MongoDB."""

    series: list[DayBucket]


class PopularCourse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: uuid.UUID
    title: str
    enrollment_count: int


class PopularCourses(BaseModel):
    courses: list[PopularCourse]


class CompletionMetrics(BaseModel):
    """Postgres-derived completion stats."""

    completion_rate: float                      # 0.0 – 1.0; ratio of completed/active+completed
    avg_completion_seconds: float | None        # null when no completions yet
    completed_enrollments: int
    active_enrollments: int


class RecentActivityItem(BaseModel):
    event_type: str
    event_key: str
    archived_at: datetime
    payload: dict


class RecentActivity(BaseModel):
    items: list[RecentActivityItem]
