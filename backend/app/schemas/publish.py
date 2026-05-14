from pydantic import BaseModel, Field


class PublishAcceptedResponse(BaseModel):
    workflow_id: str = Field(examples=["publish-550e8400-e29b-41d4-a716-446655440000"])


class PublishStatusResponse(BaseModel):
    workflow_id: str
    status: str
