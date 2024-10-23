from typing import List
from sqlalchemy import CheckConstraint, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.database.base import Base
from app.models.database.claim import ClaimModel
from app.models.database.feedback import FeedbackModel
from app.models.database.message import MessageModel


class AnalysisStatus(str, enum.Enum):
    """Status options for analysis."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DISPUTED = "disputed"


class AnalysisModel(Base):
    """Analysis database model."""

    claim_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)

    veracity_score: Mapped[float] = mapped_column(nullable=False)

    confidence_score: Mapped[float] = mapped_column(nullable=False)

    analysis_text: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[AnalysisStatus] = mapped_column(
        SQLEnum(AnalysisStatus),
        default=AnalysisStatus.PENDING,
        nullable=False,
        index=True,
        doc="Current status of the analysis",
    )

    # Relationships
    claim: Mapped["ClaimModel"] = relationship(back_populates="analyses", doc="Related claim")

    # sources: Mapped[List["SourceModel"]] = relationship(
    #     back_populates="analysis", cascade="all, delete-orphan", doc="Sources used in the analysis"
    # )

    feedback: Mapped[List["FeedbackModel"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", doc="Feedback received on this analysis"
    )
    messages: Mapped[List["MessageModel"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", doc="Messages referencing this analysis"
    )

    __table_args__ = (
        # Ensure scores are between 0 and 1
        CheckConstraint("veracity_score >= 0 AND veracity_score <= 1", name="check_veracity_score_range"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="check_confidence_score_range"),
    )
