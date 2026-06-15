from pydantic import BaseModel


class ReindexAcceptedResponse(BaseModel):
    status: str = "accepted"
    course_id: str
    task: str = "tasks.reindex_course"
