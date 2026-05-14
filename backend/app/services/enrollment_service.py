import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    AlreadyEnrolledError,
    CourseFullError,
    CourseNotFoundError,
    CourseNotPublishedError,
    EnrollmentNotFoundError,
    ForbiddenError,
    LessonNotInCourseError,
)
from app.models.course import CourseStatus
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.progress import Progress
from app.models.user import User
from app.repositories import enrollment_repo, lesson_repo, progress_repo
from app.schemas.enrollment import ProgressSummary

logger = logging.getLogger(__name__)


async def enroll(
    db: AsyncSession, *, student: User, course_id: uuid.UUID
) -> Enrollment:
    """
    Race-safe enrollment. Holds a row-level lock on the courses row for the
    duration of the request so two concurrent enrollments cannot both squeeze
    past a capacity check.

    Idempotency:
    - DB UNIQUE(student_id, course_id) catches duplicates under concurrency.
    - We convert that IntegrityError into AlreadyEnrolledError → 409.
    """
    course = await enrollment_repo.lock_course_for_enrollment(db, course_id)
    if course is None:
        raise CourseNotFoundError()

    if course.status != CourseStatus.published:
        raise CourseNotPublishedError(
            f"Cannot enroll in a {course.status.value} course"
        )

    if course.max_students is not None:
        active = await enrollment_repo.count_active(db, course_id)
        if active >= course.max_students:
            raise CourseFullError(
                f"Course has reached its capacity of {course.max_students} students"
            )

    try:
        enrollment = await enrollment_repo.create(
            db, student_id=student.id, course_id=course_id
        )
    except IntegrityError:
        # uq_enrollment_student_course — already enrolled
        await db.rollback()
        raise AlreadyEnrolledError("Already enrolled in this course")

    return enrollment


async def list_for_student(
    db: AsyncSession, student: User, *, limit: int, offset: int
) -> list[Enrollment]:
    return await enrollment_repo.list_for_student(
        db, student.id, limit=limit, offset=offset
    )


async def get_for_student(
    db: AsyncSession, enrollment_id: uuid.UUID, student: User
) -> Enrollment:
    enrollment = await enrollment_repo.get_by_id(db, enrollment_id)
    if enrollment is None:
        raise EnrollmentNotFoundError()
    if enrollment.student_id != student.id:
        raise ForbiddenError("This enrollment belongs to another student")
    return enrollment


async def list_progress(
    db: AsyncSession, *, student: User, enrollment_id: uuid.UUID
) -> list[Progress]:
    """Completed-lesson rows for one of the student's own enrollments."""
    await get_for_student(db, enrollment_id, student)
    return await progress_repo.list_for_enrollment(db, enrollment_id)


async def complete_lesson(
    db: AsyncSession,
    *,
    student: User,
    enrollment_id: uuid.UUID,
    lesson_id: uuid.UUID,
) -> Progress:
    """
    Mark a lesson as complete. Idempotent — calling twice returns the same
    Progress row (no 409). Triggers auto-completion of the enrollment when
    every lesson in the course has been completed.
    """
    enrollment = await get_for_student(db, enrollment_id, student)

    # one-shot join — cheaper than fetching the lesson + module separately
    lesson_course_id = await lesson_repo.get_course_id(db, lesson_id)
    if lesson_course_id is None:
        raise LessonNotInCourseError("Lesson not found")
    if lesson_course_id != enrollment.course_id:
        raise LessonNotInCourseError(
            "Lesson does not belong to the enrolled course"
        )

    try:
        progress = await progress_repo.create(
            db, enrollment_id=enrollment_id, lesson_id=lesson_id
        )
    except IntegrityError:
        # uq_progress_enrollment_lesson — already completed, return existing row
        await db.rollback()
        existing = await progress_repo.get_by_enrollment_and_lesson(
            db, enrollment_id, lesson_id
        )
        if existing is None:
            # extremely unlikely — would mean the row vanished between the
            # IntegrityError and the lookup. Surface as a real error.
            logger.error(
                "IntegrityError on progress insert but no existing row found "
                "for enrollment=%s lesson=%s",
                enrollment_id,
                lesson_id,
            )
            raise
        return existing

    # Auto-complete the enrollment when every lesson is done.
    # Safe to query inside this transaction — flush() above made the insert
    # visible to subsequent reads on the same session.
    total_lessons = await progress_repo.count_lessons_in_course(
        db, enrollment.course_id
    )
    if total_lessons > 0:
        completed = await progress_repo.count_for_enrollment(db, enrollment_id)
        if completed >= total_lessons and enrollment.status != EnrollmentStatus.completed:
            enrollment.status = EnrollmentStatus.completed
            enrollment.completed_at = datetime.now(timezone.utc)
            await db.flush()

    return progress


async def compute_progress_summary(
    db: AsyncSession, enrollment: Enrollment
) -> ProgressSummary:
    total = await progress_repo.count_lessons_in_course(db, enrollment.course_id)
    completed = await progress_repo.count_for_enrollment(db, enrollment.id)
    percent = (completed / total * 100.0) if total > 0 else 0.0
    return ProgressSummary(
        total_lessons=total,
        completed_lessons=completed,
        percent=round(percent, 2),
    )
