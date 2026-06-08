import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, UserRole
from app.repositories import search_repo
from app.schemas.search import SearchHit, SearchResponse
from app.services import embedding_service

logger = logging.getLogger(__name__)


async def semantic_search(
    db: AsyncSession,
    *,
    query: str,
    course_id: uuid.UUID | None,
    limit: int,
) -> SearchResponse:
    """Embed the query → vector ANN against `lesson_chunks` → top-K hits.

    ANN always returns the *nearest* chunks, even when none are actually
    relevant — so we drop anything below `rag_min_similarity`. Otherwise a
    query like "capital of france" against a movie-trailer course would still
    surface the trailer chunk at ~0% match, which looks broken.
    """
    vectors = await embedding_service.embed([query])
    hits = await search_repo.search_chunks(
        db, query_vector=vectors[0], course_id=course_id, limit=limit
    )
    relevant = [h for h in hits if h["similarity"] >= settings.rag_min_similarity]
    return SearchResponse(
        query=query,
        results=[SearchHit(**h) for h in relevant],
    )


async def global_search(
    db: AsyncSession, *, query: str, user: User, limit: int
) -> SearchResponse:
    """Search across only the courses this user may access:
      - student   → courses they're enrolled in (excludes dropped)
      - instructor → courses they own
      - admin     → all courses (no scope filter)

    This is the access-control boundary: a student can never surface chunks
    from a course they aren't enrolled in.
    """
    course_ids: list[uuid.UUID] | None
    if user.role == UserRole.admin:
        course_ids = None  # no scope → search everything
    elif user.role == UserRole.instructor:
        course_ids = await search_repo.owned_course_ids(db, user.id)
    else:  # student
        course_ids = await search_repo.enrolled_course_ids(db, user.id)

    vectors = await embedding_service.embed([query])
    hits = await search_repo.search_chunks(
        db, query_vector=vectors[0], course_ids=course_ids, limit=limit
    )
    relevant = [h for h in hits if h["similarity"] >= settings.rag_min_similarity]

    # Diagnostic — explains WHY a global search returned N results: which
    # courses were in scope, how many raw vs above-threshold hits. Grep
    # "global_search" in Loki/api logs to debug "0 results".
    top = max((h["similarity"] for h in hits), default=0.0)
    logger.info(
        "global_search user=%s role=%s accessible_courses=%s "
        "raw_hits=%d kept=%d top_sim=%.3f floor=%.2f query=%r",
        user.id, user.role.value,
        "ALL" if course_ids is None else len(course_ids),
        len(hits), len(relevant), top, settings.rag_min_similarity, query,
    )
    return SearchResponse(
        query=query,
        results=[SearchHit(**h) for h in relevant],
    )
