from uuid import UUID
from datetime import datetime
from app.models.domain.feedback import Feedback
from app.schemas.feedback_schema import FeedbackCreate


class FeedbackService:
    def create_feedback(self, feedback_create: FeedbackCreate) -> Feedback:
        return Feedback(
            id=UUID.uuid4(),
            analysis_id=feedback_create.analysis_id,
            user_id=feedback_create.user_id,
            rating=feedback_create.rating,
            comment=feedback_create.comment,
            created_at=datetime.now(),
        )

    def get_feedback(self, feedback_id: UUID) -> Feedback:
        # In a real implementation, this would fetch from a database
        pass
