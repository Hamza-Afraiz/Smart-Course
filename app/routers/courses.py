import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DBSession, InstructorUser
from app.exceptions import (
    CourseNotFoundError,
    ForbiddenError,
    InvalidStatusTransitionError,
    ModuleNotFoundError,
    OrderIndexConflictError,
)
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate
from app.schemas.lesson import LessonCreate, LessonResponse
from app.schemas.module import ModuleCreate, ModuleResponse
from app.services import course_service, lesson_service, module_service

router = APIRouter(tags=["Courses"])


# ── Courses ───────────────────────────────────────────────────────────────────

@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    instructor: InstructorUser,
    db: DBSession,
) -> CourseResponse:
    return await course_service.create(
        db,
        instructor=instructor,
        title=payload.title,
        description=payload.description,
        max_students=payload.max_students,
    )


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    _user: CurrentUser,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[CourseResponse]:
    return await course_service.list_published(db, limit=limit, offset=offset)


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: uuid.UUID, current_user: CurrentUser, db: DBSession) -> CourseResponse:
    try:
        return await course_service.get_for_view(db, course_id, current_user)
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> CourseResponse:
    try:
        return await course_service.update(
            db,
            course_id=course_id,
            actor=current_user,
            title=payload.title,
            description=payload.description,
            max_students=payload.max_students,
            status=payload.status,
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{course_id}", response_model=CourseResponse)
async def delete_course(course_id: uuid.UUID, current_user: CurrentUser, db: DBSession) -> CourseResponse:
    try:
        return await course_service.soft_delete(db, course_id=course_id, actor=current_user)
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ── Modules ───────────────────────────────────────────────────────────────────

@router.post(
    "/{course_id}/modules",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_module(
    course_id: uuid.UUID,
    payload: ModuleCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> ModuleResponse:
    try:
        return await module_service.create(
            db,
            course_id=course_id,
            actor=current_user,
            title=payload.title,
            order_index=payload.order_index,
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except OrderIndexConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{course_id}/modules", response_model=list[ModuleResponse])
async def list_modules(course_id: uuid.UUID, current_user: CurrentUser, db: DBSession) -> list[ModuleResponse]:
    try:
        return await module_service.list_for_course(db, course_id, current_user)
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")


# ── Lessons ───────────────────────────────────────────────────────────────────

@router.post(
    "/{course_id}/modules/{module_id}/lessons",
    response_model=LessonResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_lesson(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    payload: LessonCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> LessonResponse:
    try:
        return await lesson_service.create(
            db,
            course_id=course_id,
            module_id=module_id,
            actor=current_user,
            title=payload.title,
            order_index=payload.order_index,
            content_type=payload.content_type,
            content_url=payload.content_url,
            duration_seconds=payload.duration_seconds,
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except ModuleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except OrderIndexConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
