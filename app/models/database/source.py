from typing import Optional
from sqlalchemy import CheckConstraint, String, Text, Float, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.database.analysis import AnalysisModel
from app.models.database.base import Base
from app.models.database.domain import DomainModel


class SourceModel(Base):
    """Source database model."""

    analysis_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis.id"),
        nullable=False,
        index=True,
        doc="Reference to the analysis using this source",
    )

    url: Mapped[str] = mapped_column(String(2048), nullable=False, doc="Source URL")  # Max URL length
    title: Mapped[str] = mapped_column(String(512), nullable=False, doc="Source title")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, doc="Relevant text snippet from source")
    domain_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domains.id"), nullable=True, index=True, doc="Reference to the source domain"
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Full source content if available")
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False, doc="Source credibility score (0-1)")

    # Relationships
    analysis: Mapped["AnalysisModel"] = relationship(back_populates="sources", doc="Related analysis")
    domain: Mapped[Optional["DomainModel"]] = relationship(doc="Related domain")

    __table_args__ = (
        CheckConstraint(
            "credibility_score >= 0 AND credibility_score <= 1", name="check_source_credibility_score_range"
        ),
        # Indexes for common queries
        Index("idx_source_url_hash", text("md5(url)"), unique=True),
    )
