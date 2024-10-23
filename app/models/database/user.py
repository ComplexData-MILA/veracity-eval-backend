from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base
from app.models.database.claim import ClaimModel
from app.models.database.conversation import ConversationModel
from app.models.database.feedback import FeedbackModel


class UserModel(Base):
    """User database model."""

    auth0_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    # Relationships
    claims: Mapped[List["ClaimModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[List["ConversationModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    feedback: Mapped[List["FeedbackModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
