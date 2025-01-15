from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime
from uuid import UUID


class ClaimCreate(BaseModel):
    """Schema for creating a claim."""

    claim_text: str
    context: str
    language: str = "english"


class ClaimStatusUpdate(BaseModel):
    """Schema for updating claim status."""

    status: str


class ClaimRead(BaseModel):
    """Schema for reading a claim."""

    id: UUID
    user_id: UUID
    claim_text: str
    context: str
    status: str
    language: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClaimList(BaseModel):
    """Schema for paginated claim list."""

    items: List[ClaimRead]
    total: int
    limit: int
    offset: int
