from typing import Optional
from sqlalchemy import Index, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.database.base import Base
from app.models.database.user import UserModel


class FeedbackModel(Base):
    """Feedback database model."""

    analysis_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    rating: Mapped[float] = mapped_column(nullable=False)

    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    # analysis: Mapped["AnalysisModel"] = relationship(back_populates="feedback", doc="Related analysis")

    user: Mapped["UserModel"] = relationship(back_populates="feedback")

    __table_args__ = (
        # Ensure rating is between 1 and 5
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
        # One feedback per user per analysis
        Index("idx_unique_user_analysis", analysis_id, user_id, unique=True),
    )
