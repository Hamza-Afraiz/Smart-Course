import uuid

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.dependencies import CurrentUser, DBSession, InstructorUser, StudentUser
from app.exceptions import (
    AlreadyEnrolledError,
    CourseFullError,
    CourseNotFoundError,
    CourseNotPublishedError,
    ForbiddenError,
    InvalidStatusTransitionError,
    ModuleNotFoundError,
    OrderIndexConflictError,
    PublishWorkflowInProgressError,
    TemporalUnavailableError,
    WorkflowNotFoundError,
)
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate
from app.schemas.enrollment import EnrollmentResponse
from app.schemas.lesson import LessonCreate, LessonResponse
from app.schemas.module import ModuleCreate, ModuleResponse
from app.schemas.publish import PublishAcceptedResponse, PublishStatusResponse
from app.services import (
    course_service,
    enrollment_service,
    lesson_service,
    module_service,
    publish_service,
)

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


# declared before /{course_id} so "mine" is not parsed as a UUID path param
@router.get("/mine", response_model=list[CourseResponse])
async def list_my_courses(
    instructor: InstructorUser,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[CourseResponse]:
    return await course_service.list_owned(
        db, instructor=instructor, limit=limit, offset=offset
    )


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


# ── Publishing (Temporal) ─────────────────────────────────────────────────────

@router.post(
    "/{course_id}/publish",
    response_model=PublishAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_course(
    course_id: uuid.UUID,
    instructor: InstructorUser,
    db: DBSession,
    request: Request,
) -> PublishAcceptedResponse:
    client = getattr(request.app.state, "temporal_client", None)
    try:
        wf_id = await publish_service.start_publish_workflow(
            client, db, course_id=course_id, actor=instructor
        )
        return PublishAcceptedResponse(workflow_id=wf_id)
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemporalUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except PublishWorkflowInProgressError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/{course_id}/publish/status",
    response_model=PublishStatusResponse,
)
async def publish_course_status(
    course_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    workflow_id: str | None = Query(
        None,
        description="Temporal workflow id (default: publish-{course_id})",
    ),
) -> PublishStatusResponse:
    try:
        await course_service.get_for_view(db, course_id, current_user)
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    wid = workflow_id or publish_service.workflow_id_for_course(course_id)
    client = getattr(request.app.state, "temporal_client", None)
    try:
        st = await publish_service.describe_publish_workflow(client, wid)
        return PublishStatusResponse(workflow_id=wid, status=st)
    except TemporalUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Publish workflow not found"
        )


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


# ── Enrollment ────────────────────────────────────────────────────────────────

@router.post(
    "/{course_id}/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_in_course(
    course_id: uuid.UUID,
    student: StudentUser,
    db: DBSession,
) -> EnrollmentResponse:
    try:
        return await enrollment_service.enroll(
            db, student=student, course_id=course_id
        )
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )
    except CourseNotPublishedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CourseFullError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AlreadyEnrolledError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


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


@router.get(
    "/{course_id}/modules/{module_id}/lessons",
    response_model=list[LessonResponse],
)
async def list_lessons(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> list[LessonResponse]:
    try:
        return await lesson_service.list_for_module(
            db, course_id=course_id, module_id=module_id, viewer=current_user
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except ModuleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
