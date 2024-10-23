from typing import Optional
from sqlalchemy import CheckConstraint, String, Text, Float, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database.base import Base


class DomainModel(Base):
    """Domain database model for tracking website credibility."""

    domain_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_reliable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    __table_args__ = (
        CheckConstraint("credibility_score >= 0 AND credibility_score <= 1", name="check_credibility_score_range"),
        # Full text search index for domain name and description
        Index(
            "idx_domain_search",
            domain_name,
            description,
            postgresql_using="gin",
            postgresql_ops={"domain_name": "gin_trgm_ops", "description": "gin_trgm_ops"},
        ),
    )
