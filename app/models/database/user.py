from datetime import datetime
from typing import List, Optional
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.database.base import Base
from app.models.database import ConversationModel


class UserModel(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    auth0_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    conversations: Mapped[List["ConversationModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    # claims: Mapped[List["ClaimModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    # feedback: Mapped[List["FeedbackModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    is_active: Mapped[bool] = mapped_column(default=True)

    def __repr__(self) -> str:
        return f"User(id={self.id}, username={self.username}, email={self.email})"
