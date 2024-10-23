from datetime import UTC, datetime
from typing import List, Optional
from sqlalchemy import ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.database.base import Base, TimestampMixin
from app.models.database.models import ClaimConversationModel
from app.models.database.models.user import UserModel


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ConversationModel(Base, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(default=datetime.now(UTC), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        SQLEnum(ConversationStatus), default=ConversationStatus.ACTIVE, nullable=False, index=True
    )

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="conversations")
    # messages: Mapped[List["MessageModel"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    claim_conversations: Mapped[List["ClaimConversationModel"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"Conversation(id={self.id}, user_id={self.user_id}, "
            f"status={self.status}, start_time={self.start_time})"
        )
