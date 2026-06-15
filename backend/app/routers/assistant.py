import json
import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, DBSession, InstructorUser
from app.exceptions import CourseNotFoundError, ForbiddenError
from app.schemas.assistant import AskRequest, GenerateRequest
from app.services import course_service, rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Assistant"])


@router.post("/ask")
async def ask(
    payload: AskRequest,
    _user: CurrentUser,
    db: DBSession,
) -> StreamingResponse:
    """RAG Q&A over a course's content. Streams the answer as Server-Sent
    Events; each frame's data is a JSON-encoded token (so newlines/markdown in
    the answer don't break SSE framing). A final `[DONE]` frame closes it.

    Grounded: the answer comes only from this course's retrieved chunks; if
    nothing relevant is found the assistant says so instead of guessing.
    """

    async def event_stream():
        try:
            async for token in rag_service.answer_stream(
                db, question=payload.question, course_id=payload.course_id
            ):
                yield f"data: {json.dumps(token)}\n\n"
        except Exception:
            logger.exception("assistant: generation failed")
            yield f"data: {json.dumps('[error] the assistant is unavailable right now')}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate")
async def generate(
    payload: GenerateRequest,
    user: InstructorUser,
    db: DBSession,
) -> StreamingResponse:
    """Instructor-only: stream a lesson/course summary or quiz from indexed content.

    Requires course ownership (or admin). Content must exist in `lesson_chunks`
    — i.e. the course has been published at least once so the Temporal pipeline
    could extract, chunk, and embed lessons.
    """
    try:
        await course_service.get_for_modify(db, payload.course_id, user)
    except CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    async def event_stream():
        try:
            async for token in rag_service.generate_stream(
                db,
                course_id=payload.course_id,
                lesson_id=payload.lesson_id,
                kind=payload.kind,
                actor=user,
            ):
                yield f"data: {json.dumps(token)}\n\n"
        except Exception:
            logger.exception("assistant: instructor generation failed")
            yield f"data: {json.dumps('[error] generation is unavailable right now')}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

