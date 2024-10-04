from uuid import UUID
from datetime import datetime


class Analysis:
    def __init__(
        self,
        id: UUID,
        claim_id: UUID,
        veracity_score: float,
        confidence_score: float,
        analysis_text: str,
        created_at: datetime,
    ):
        self.id = id
        self.claim_id = claim_id
        self.veracity_score = veracity_score
        self.confidence_score = confidence_score
        self.analysis_text = analysis_text
        self.created_at = created_at
