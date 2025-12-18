from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID
import pickle

from app.models.database.models import AnalysisModel, AnalysisStatus
from app.models.domain.feedback import Feedback
from app.models.domain.search import Search

@dataclass
class LogProbsData:
    anth_conf_score: float
    tokens: List[str]
    probs: List[float]
    alternatives: List[Dict[str, float]]


@dataclass
class Analysis:
    """Domain model for claim analysis."""

    id: UUID
    claim_id: UUID
    veracity_score: float
    confidence_score: float
    analysis_text: str
    status: str
    created_at: datetime
    updated_at: datetime
    log_probs: Optional[LogProbsData] = None
    searches: Optional[List["Search"]] = None
    feedback: Optional[List["Feedback"]] = None

    @classmethod
    def from_model(cls, model: "AnalysisModel") -> "Analysis":
        """Create domain model from database model."""
        
        log_probs_obj = None
        if model.log_probs:
            try:
                log_probs_obj = pickle.loads(model.log_probs)
            except Exception:
                # Fallback in case unpickling fails (e.g., corrupt data)
                log_probs_obj = None
        
        return cls(
            id=model.id,
            claim_id=model.claim_id,
            veracity_score=model.veracity_score,
            confidence_score=model.confidence_score,
            analysis_text=model.analysis_text,
            status=model.status.value,
            created_at=model.created_at,
            updated_at=model.updated_at,
            log_probs=log_probs_obj,
            searches=[Search.from_model(s) for s in model.searches] if model.searches else None,
            feedback=[Feedback.from_model(f) for f in model.feedbacks] if model.feedbacks else None,
        )

    @classmethod
    def from_model_safe(cls, model: "AnalysisModel") -> "Analysis":
        """Create domain model from database model, explicitly ignoring relationships."""
        
        log_probs_obj = None
        if model.log_probs:
            try:
                log_probs_obj = pickle.loads(model.log_probs)
            except Exception:
                log_probs_obj = None
        
        return cls(
            id=model.id,
            claim_id=model.claim_id,
            veracity_score=model.veracity_score,
            confidence_score=model.confidence_score,
            analysis_text=model.analysis_text,
            status=model.status.value,
            created_at=model.created_at,
            updated_at=model.updated_at,
            log_probs=log_probs_obj,
            # empty initalization (they are empty at creation)
            searches=None, 
            feedback=None,
        )
    
    def to_model(self) -> "AnalysisModel":
        """Convert to database model."""

        log_probs_bytes = None
        if self.log_probs:
            log_probs_bytes = pickle.dumps(self.log_probs)

        return AnalysisModel(
            id=self.id,
            claim_id=self.claim_id,
            veracity_score=self.veracity_score,
            confidence_score=self.confidence_score,
            analysis_text=self.analysis_text,
            status=AnalysisStatus(self.status),
            log_probs=log_probs_bytes,
        )
