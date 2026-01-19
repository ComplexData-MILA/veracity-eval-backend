from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional
from app.models.domain.analysis import LogProbsData


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
    log_probs: Optional[LogProbsData]

    model_config = ConfigDict(from_attributes=True)


class AnalysisList(BaseModel):
    items: list[AnalysisRead]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)
