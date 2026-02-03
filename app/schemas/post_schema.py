from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, validator

class PostCreate(BaseModel):
    discussion_id: UUID = Field(..., description="ID of the discussion this post belongs to")
    text: str = Field(..., min_length=1, max_length=10000)

class PostUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)

# TODO confirm with Dorsaf
class PostVote(BaseModel):
    vote_type: str = Field(..., pattern="^(up|down)$", description="Must be 'up' or 'down'")

class PostResponse(BaseModel):
    id: UUID
    discussion_id: UUID
    user_id: UUID
    text: str
    up_votes: int
    down_votes: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True