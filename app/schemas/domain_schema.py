from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class DomainCreate(BaseModel):
    domain_name: str
    credibility_score: float
    is_reliable: bool
    description: str = None


class DomainRead(BaseModel):
    id: UUID
    domain_name: str
    credibility_score: float
    is_reliable: bool
    description: str = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
