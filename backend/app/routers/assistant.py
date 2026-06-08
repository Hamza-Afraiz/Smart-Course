import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, DBSession
from app.schemas.assistant import AskRequest
from app.services import rag_service

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
