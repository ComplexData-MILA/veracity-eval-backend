from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class ClaimCreate(BaseModel):
    user_id: UUID
    claim_text: str
    context: str


class ClaimRead(BaseModel):
    id: UUID
    user_id: UUID
    claim_text: str
    context: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
