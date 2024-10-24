from datetime import datetime
from uuid import UUID


class LLMResponse:
    """Domain model for LLM response"""

    def __init__(self, id: UUID, text: str, confidence_score: float, created_at: datetime):
        self.id = id
        self.text = text
        self.confidence_score = confidence_score
        self.created_at = created_at
