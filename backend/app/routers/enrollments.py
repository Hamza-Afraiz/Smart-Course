import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DBSession, StudentUser
from app.exceptions import (
    EnrollmentNotFoundError,
    ForbiddenError,
    LessonNotInCourseError,
)
from app.schemas.enrollment import EnrollmentWithCourse, ProgressSummary
from app.schemas.progress import ProgressResponse
from app.services import enrollment_service

router = APIRouter(tags=["Enrollments"])


@router.get("/me", response_model=list[EnrollmentWithCourse])
async def list_my_enrollments(
    student: StudentUser,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[EnrollmentWithCourse]:
    enrollments = await enrollment_service.list_for_student(
        db, student, limit=limit, offset=offset
    )
    out: list[EnrollmentWithCourse] = []
    for e in enrollments:
        summary = await enrollment_service.compute_progress_summary(db, e)
        out.append(
            EnrollmentWithCourse(
                id=e.id,
                student_id=e.student_id,
                course_id=e.course_id,
                status=e.status,
                enrolled_at=e.enrolled_at,
                completed_at=e.completed_at,
                course_title=e.course.title,
                progress_summary=summary,
            )
        )
    return out


@router.get("/{enrollment_id}/progress", response_model=list[ProgressResponse])
async def list_enrollment_progress(
    enrollment_id: uuid.UUID,
    student: StudentUser,
    db: DBSession,
) -> list[ProgressResponse]:
    try:
        return await enrollment_service.list_progress(
            db, student=student, enrollment_id=enrollment_id
        )
    except EnrollmentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found"
        )
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post(
    "/{enrollment_id}/progress/{lesson_id}",
    response_model=ProgressResponse,
    status_code=status.HTTP_201_CREATED,
)
async def mark_lesson_complete(
    enrollment_id: uuid.UUID,
    lesson_id: uuid.UUID,
    student: StudentUser,
    db: DBSession,
) -> ProgressResponse:
    try:
        return await enrollment_service.complete_lesson(
            db,
            student=student,
            enrollment_id=enrollment_id,
            lesson_id=lesson_id,
        )
    except EnrollmentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found"
        )
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LessonNotInCourseError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
