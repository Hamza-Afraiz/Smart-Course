from fastapi import APIRouter

from app.dependencies import CurrentUser, DBSession
from app.schemas.search import GlobalSearchRequest, SearchRequest, SearchResponse
from app.services import search_service

router = APIRouter(tags=["Search"])


@router.post("/semantic", response_model=SearchResponse)
async def semantic_search(
    payload: SearchRequest,
    _user: CurrentUser,
    db: DBSession,
) -> SearchResponse:
    """Semantic search over indexed lesson chunks.

    Any authenticated user can search; pass `course_id` to scope to one course.
    """
    return await search_service.semantic_search(
        db,
        query=payload.query,
        course_id=payload.course_id,
        limit=payload.limit,
    )


@router.post("/my", response_model=SearchResponse)
async def search_my_courses(
    payload: GlobalSearchRequest,
    user: CurrentUser,
    db: DBSession,
) -> SearchResponse:
    """Global semantic search across only the courses the caller can access
    (student → enrolled, instructor → owned, admin → all). Never leaks content
    from courses the user isn't enrolled in / doesn't own.
    """
    return await search_service.global_search(
        db, query=payload.query, user=user, limit=payload.limit
    )
