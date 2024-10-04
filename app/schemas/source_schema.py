from pydantic import BaseModel, ConfigDict
from uuid import UUID


class SourceCreate(BaseModel):
    analysis_id: UUID
    url: str
    title: str
    snippet: str
    credibility_score: float


class SourceRead(BaseModel):
    id: UUID
    analysis_id: UUID
    url: str
    title: str
    snippet: str
    credibility_score: float

    model_config = ConfigDict(from_attributes=True)
