from fastapi import APIRouter, Query, status

from app.dependencies import CurrentUser, DBSession, StudentUser
from app.schemas.certificate import CertificateResponse
from app.services import certificate_service

router = APIRouter(tags=["Certificates"])


@router.get("/me", response_model=list[CertificateResponse])
async def list_my_certificates(
    student: StudentUser,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[CertificateResponse]:
    certs = await certificate_service.list_for_student(
        db, student.id, limit=limit, offset=offset
    )
    return [
        CertificateResponse(
            id=c.id,
            enrollment_id=c.enrollment_id,
            student_id=c.student_id,
            course_id=c.course_id,
            issued_at=c.issued_at,
            certificate_url=c.certificate_url,
            course_title=c.course.title if c.course else None,
        )
        for c in certs
    ]
