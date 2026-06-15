import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseStatus, course_prerequisites
from app.models.enrollment import Enrollment, EnrollmentStatus


async def recommend_for_student(
    db: AsyncSession, *, student_id: uuid.UUID, limit: int
) -> list[tuple[Course, int]]:
    """Published courses the student can enrol in right now, most popular first.

    Eligible = published, not already enrolled, and every prerequisite completed.
    Popularity = total enrolment count (Postgres is the source of truth — the Mongo
    event log can double-count redeliveries, so it's wrong for an exact ranking).
    """
    my_courses = (
        select(Enrollment.course_id)
        .where(Enrollment.student_id == student_id)
        .scalar_subquery()
    )
    my_completed = (
        select(Enrollment.course_id)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.completed,
        )
        .scalar_subquery()
    )
    # courses carrying at least one prerequisite the student hasn't completed
    blocked = (
        select(course_prerequisites.c.course_id)
        .where(course_prerequisites.c.prerequisite_id.not_in(my_completed))
        .scalar_subquery()
    )
    result = await db.execute(
        select(Course, func.count(Enrollment.id).label("popularity"))
        .outerjoin(Enrollment, Enrollment.course_id == Course.id)
        .where(
            Course.status == CourseStatus.published,
            Course.id.not_in(my_courses),
            Course.id.not_in(blocked),
        )
        .group_by(Course.id)
        .order_by(func.count(Enrollment.id).desc(), Course.created_at.desc())
        .limit(limit)
    )
    return [(course, int(popularity)) for course, popularity in result.all()]
