from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class AnalysisCreate(BaseModel):
    claim_id: UUID
    veracity_score: float
    confidence_score: float
    analysis_text: str


class AnalysisRead(BaseModel):
    id: UUID
    claim_id: UUID
    veracity_score: float
    confidence_score: float
    analysis_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
