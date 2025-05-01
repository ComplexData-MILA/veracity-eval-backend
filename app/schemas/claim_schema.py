from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ClaimCreate(BaseModel):
    """Schema for creating a claim."""

    claim_text: str
    context: str
    language: str = "english"
    batch_user_id: str = None
    batch_post_id: str = None


class ClaimStatusUpdate(BaseModel):
    """Schema for updating claim status."""

    status: str


class ClaimEmbeddingUpdate(BaseModel):
    """Schema for updating claim status."""

    embedding: List[float] = None


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
    batch_user_id: Optional[str]
    batch_post_id: Optional[str]
    embedding: Optional[List[float]]

    model_config = ConfigDict(from_attributes=True)


class ClaimList(BaseModel):
    """Schema for paginated claim list."""

    items: List[ClaimRead]
    total: int
    limit: int
    offset: int


class WordCloudRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    language: str = "english"


class SuccessResult(BaseModel):
    claim_id: UUID
    analysis_id: UUID
    veracity_score: float
    average_source_credibility: float
    num_sources: int
    batch_user_id: Optional[str]
    batch_post_id: Optional[str]


class FailureResult(BaseModel):
    claim_id: UUID
    status: str
    message: str


class BatchAnalysisResponse(BaseModel):
    successes: List[SuccessResult]
    failures: List[FailureResult]
