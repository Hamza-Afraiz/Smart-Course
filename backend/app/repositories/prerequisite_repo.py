import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, course_prerequisites
from app.models.enrollment import Enrollment, EnrollmentStatus


async def add(
    db: AsyncSession, *, course_id: uuid.UUID, prerequisite_id: uuid.UUID
) -> None:
    """Insert a prerequisite edge. Idempotent — a duplicate edge is a no-op."""
    await db.execute(
        pg_insert(course_prerequisites)
        .values(course_id=course_id, prerequisite_id=prerequisite_id)
        .on_conflict_do_nothing()
    )


async def remove(
    db: AsyncSession, *, course_id: uuid.UUID, prerequisite_id: uuid.UUID
) -> bool:
    result = await db.execute(
        delete(course_prerequisites).where(
            course_prerequisites.c.course_id == course_id,
            course_prerequisites.c.prerequisite_id == prerequisite_id,
        )
    )
    return result.rowcount > 0


async def list_prerequisites(db: AsyncSession, course_id: uuid.UUID) -> list[Course]:
    result = await db.execute(
        select(Course)
        .join(course_prerequisites, Course.id == course_prerequisites.c.prerequisite_id)
        .where(course_prerequisites.c.course_id == course_id)
        .order_by(Course.title)
    )
    return list(result.scalars().all())


async def unmet_prerequisites(
    db: AsyncSession, *, student_id: uuid.UUID, course_id: uuid.UUID
) -> list[Course]:
    """Prerequisite courses the student has NOT completed yet (the enroll gate)."""
    completed = (
        select(Enrollment.course_id)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.completed,
        )
        .scalar_subquery()
    )
    result = await db.execute(
        select(Course)
        .join(course_prerequisites, Course.id == course_prerequisites.c.prerequisite_id)
        .where(
            course_prerequisites.c.course_id == course_id,
            Course.id.not_in(completed),
        )
        .order_by(Course.title)
    )
    return list(result.scalars().all())


# Adding edge "course requires prerequisite" is safe unless the prerequisite
# already (transitively) requires the course — that closes a loop and makes both
# courses un-enrollable. Walk the requirement graph from the prerequisite node;
# if we reach the course, it's a cycle. Recursive CTE so depth is unbounded.
_CYCLE_SQL = text(
    """
    WITH RECURSIVE deps AS (
        SELECT prerequisite_id
        FROM course_prerequisites
        WHERE course_id = :start
        UNION
        SELECT cp.prerequisite_id
        FROM course_prerequisites cp
        JOIN deps ON cp.course_id = deps.prerequisite_id
    )
    SELECT 1 FROM deps WHERE prerequisite_id = :target LIMIT 1
    """
)


async def would_create_cycle(
    db: AsyncSession, *, course_id: uuid.UUID, prerequisite_id: uuid.UUID
) -> bool:
    result = await db.execute(
        _CYCLE_SQL, {"start": prerequisite_id, "target": course_id}
    )
    return result.first() is not None
