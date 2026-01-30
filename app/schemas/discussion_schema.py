from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class DiscussionResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    analysis_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Allows mapping from your Domain/DB models


class PaginatedDiscussionsResponse(BaseModel):
    items: List[DiscussionResponse]
    total: int
    limit: int
    offset: int


class DiscussionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    analysis_id: Optional[UUID] = None

    class Config:
        from_attributes = True
