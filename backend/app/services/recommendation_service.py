from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import recommendation_repo
from app.schemas.recommendation import CourseRecommendation


async def recommend(
    db: AsyncSession, *, student: User, limit: int
) -> list[CourseRecommendation]:
    rows = await recommendation_repo.recommend_for_student(
        db, student_id=student.id, limit=limit
    )
    return [
        CourseRecommendation(
            id=course.id,
            title=course.title,
            description=course.description,
            instructor_id=course.instructor_id,
            status=course.status,
            popularity=popularity,
        )
        for course, popularity in rows
    ]
