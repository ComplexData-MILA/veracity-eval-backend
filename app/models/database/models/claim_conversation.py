from datetime import UTC, datetime
from typing import Optional
from sqlalchemy import ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.database.base import Base, TimestampMixin
from app.models.database.models.conversation import ConversationStatus, ConversationModel


class ClaimConversationModel(Base, TimestampMixin):
    __tablename__ = "claim_conversations"

    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    claim_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(default=datetime.now(UTC), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        SQLEnum(ConversationStatus), default=ConversationStatus.ACTIVE, nullable=False
    )

    # Relationships
    conversation: Mapped["ConversationModel"] = relationship(back_populates="claim_conversations")
    # claim: Mapped["ClaimModel"] = relationship(back_populates="claim_conversations")
    # messages: Mapped[List["MessageModel"]] = relationship(
    #     back_populates="claim_conversation", cascade="all, delete-orphan"
    # )

    def __repr__(self) -> str:
        return (
            f"ClaimConversation(id={self.id}, conversation_id={self.conversation_id}, "
            f"claim_id={self.claim_id}, status={self.status})"
        )
