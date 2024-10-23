from datetime import datetime, UTC
from typing import Optional
from sqlalchemy import Text, JSON, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.database.base import Base
from app.models.database.claim import ClaimModel
from app.models.database.claim_conversation import ClaimConversationModel
from app.models.database.conversation import ConversationModel


class MessageSenderType(str, enum.Enum):
    """Types of message senders."""

    USER = "user"
    BOT = "bot"
    SYSTEM = "system"


class MessageModel(Base):
    """Message database model."""

    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )

    sender_type: Mapped[MessageSenderType] = mapped_column(SQLEnum(MessageSenderType), nullable=False, index=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(default=datetime.now(UTC), nullable=False, index=True)

    claim_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id"), nullable=True, index=True
    )

    analysis_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis.id"),
        nullable=True,
        index=True,
    )

    claim_conversation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim_conversations.id"), nullable=True, index=True
    )

    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    conversation: Mapped["ConversationModel"] = relationship(back_populates="messages")
    claim: Mapped[Optional["ClaimModel"]] = relationship(back_populates="messages")

    # analysis: Mapped[Optional["AnalysisModel"]] = relationship(
    #     back_populates="messages", doc="Related analysis, if any"
    # )

    claim_conversation: Mapped[Optional["ClaimConversationModel"]] = relationship(
        back_populates="messages", doc="Related claim conversation, if any"
    )

    __table_args__ = (
        Index("idx_message_conversation_timestamp", conversation_id, timestamp.desc()),
        Index("idx_message_claim_conversation_timestamp", claim_conversation_id, timestamp.desc()),
    )
