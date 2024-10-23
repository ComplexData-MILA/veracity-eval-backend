from typing import List
from sqlalchemy import Text, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.database.base import Base
from app.models.database.claim_conversation import ClaimConversationModel
from app.models.database.message import MessageModel
from app.models.database.user import UserModel


class ClaimStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    DISPUTED = "disputed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ClaimModel(Base):
    """Database model for claims."""

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        doc="Reference to the user who created this claim",
    )

    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ClaimStatus] = mapped_column(
        SQLEnum(ClaimStatus), default=ClaimStatus.PENDING, nullable=False, index=True
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="claims")

    # analyses: Mapped[List["AnalysisModel"]] = relationship(
    #     back_populates="claim", cascade="all, delete-orphan", "
    # )

    claim_conversations: Mapped[List["ClaimConversationModel"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    messages: Mapped[List["MessageModel"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", doc="Messages referencing this claim"
    )
