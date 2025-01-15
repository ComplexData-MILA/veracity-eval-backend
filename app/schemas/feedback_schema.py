from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, List


class FeedbackCreate(BaseModel):
    analysis_id: UUID
    rating: float
    comment: str
    labels: Optional[List[int]] = None


class FeedbackRead(BaseModel):
    id: UUID
    analysis_id: UUID
    user_id: UUID
    rating: float
    comment: str
    created_at: datetime
    labels: Optional[List[int]] = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackList(BaseModel):
    items: list[FeedbackRead]
    total: int
    limit: int
    offset: int


class FeedbackUpdate(BaseModel):
    rating: float
    comment: str
    labels: Optional[List[int]] = None
