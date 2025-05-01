from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional
from app.schemas.domain_schema import DomainRead


class SourceCreate(BaseModel):
    search_id: UUID
    url: str
    title: str
    snippet: str
    credibility_score: Optional[float]


class SourceRead(BaseModel):
    id: UUID
    search_id: UUID
    url: str
    title: str
    snippet: str
    credibility_score: Optional[float]
    domain: Optional[DomainRead]
    content: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class SourceList(BaseModel):
    items: list[SourceRead]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)
