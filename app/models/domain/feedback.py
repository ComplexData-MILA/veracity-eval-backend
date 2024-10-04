from uuid import UUID
from datetime import datetime


class Feedback:
    def __init__(self, id: UUID, analysis_id: UUID, user_id: UUID, rating: float, comment: str, created_at: datetime):
        self.id = id
        self.analysis_id = analysis_id
        self.user_id = user_id
        self.rating = rating
        self.comment = comment
        self.created_at = created_at
