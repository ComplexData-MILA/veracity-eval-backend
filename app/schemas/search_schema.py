from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional


class SearchCreate(BaseModel):
    analysis_id: UUID
    prompt: str
    summary: Optional[str]


class SearchRead(BaseModel):
    id: UUID
    analysis_id: UUID
    prompt: str
    summary: str

    model_config = ConfigDict(from_attributes=True)


class SearchList(BaseModel):
    items: list[SearchRead]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)
