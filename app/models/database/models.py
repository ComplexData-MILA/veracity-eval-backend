import enum
from datetime import UTC, datetime
from typing import Optional, List
import uuid
from sqlalchemy import (
    UUID,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    String,
    Boolean,
    Text,
    Enum as SQLEnum,
    ForeignKey,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base


class ConversationStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class MessageSenderType(str, enum.Enum):
    user = "user"
    bot = "bot"
    system = "system"


class ClaimStatus(str, enum.Enum):
    pending = "pending"
    analyzing = "analyzing"
    analyzed = "analyzed"
    disputed = "disputed"
    verified = "verified"
    rejected = "rejected"
    failed = "failed"


class AnalysisStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    disputed = "disputed"


class UserModel(Base):
    auth0_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    claims: Mapped[List["ClaimModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[List["ConversationModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    feedbacks: Mapped[List["FeedbackModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class DomainModel(Base):
    domain_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_reliable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    __table_args__ = (
        CheckConstraint("credibility_score >= 0 AND credibility_score <= 1", name="check_credibility_score_range"),
    )


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        SQLEnum(ConversationStatus, name="conversation_status"),
        default=ConversationStatus.active,
        nullable=False,
        index=True,
    )

    user: Mapped["UserModel"] = relationship(back_populates="conversations")
    messages: Mapped[List["MessageModel"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    claim_conversations: Mapped[List["ClaimConversationModel"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ClaimModel(Base):
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        doc="Reference to the user who created this claim",
    )

    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(
        SQLEnum(ClaimStatus, name="claim_status"), default=ClaimStatus.pending, nullable=False
    )
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default='english')

    user: Mapped["UserModel"] = relationship(back_populates="claims")
    analyses: Mapped[List["AnalysisModel"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    claim_conversations: Mapped[List["ClaimConversationModel"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    messages: Mapped[List["MessageModel"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class AnalysisModel(Base):
    __tablename__ = "analysis"

    claim_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    veracity_score: Mapped[float] = mapped_column(nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=True)
    analysis_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(
        SQLEnum(AnalysisStatus, name="analysis_status"),
        default=AnalysisStatus.pending,
        nullable=False,
        index=True,
    )

    claim: Mapped["ClaimModel"] = relationship(back_populates="analyses", doc="Related claim")
    sources: Mapped[List["SourceModel"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")
    feedbacks: Mapped[List["FeedbackModel"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        primaryjoin="FeedbackModel.analysis_id == AnalysisModel.id",
    )
    messages: Mapped[List["MessageModel"]] = relationship(back_populates="analysis", doc="Related analysis, if any")

    __table_args__ = (
        CheckConstraint("veracity_score >= 0 AND veracity_score <= 1", name="check_veracity_score_range"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="check_confidence_score_range"),
    )


class SourceModel(Base):
    __tablename__ = "sources"

    analysis_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    snippet: Mapped[str] = mapped_column(Text, nullable=True)
    domain_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domains.id"), nullable=True, index=True
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credibility_score: Mapped[float] = mapped_column(Float, nullable=True)

    analysis: Mapped["AnalysisModel"] = relationship(back_populates="sources")
    domain: Mapped[Optional["DomainModel"]] = relationship(
        "DomainModel",
        lazy="joined",
    )

    __table_args__ = (
        CheckConstraint(
            "(credibility_score IS NULL OR (credibility_score >= 0 AND credibility_score <= 1))", name="check_source_credibility_score_range"
        ),
        Index("idx_source_url_hash", text("md5(url)"), unique=True),
    )


class FeedbackModel(Base):
    __tablename__ = "feedback"

    analysis_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    rating: Mapped[float] = mapped_column(nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    analysis: Mapped["AnalysisModel"] = relationship(
        "AnalysisModel",
        back_populates="feedbacks",
        primaryjoin="FeedbackModel.analysis_id == AnalysisModel.id",
        doc="Related analysis",
    )
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="feedbacks")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
        Index("ix_unique_user_analysis", analysis_id, user_id, unique=True),
    )


class ClaimConversationModel(Base):
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete='CASCADE'), nullable=False, index=True
    )
    claim_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id", ondelete='CASCADE'), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        SQLEnum(ConversationStatus, name="conversation_status"),
        default=ConversationStatus.active,
        nullable=False,
        index=True,
    )

    conversation: Mapped["ConversationModel"] = relationship(back_populates="claim_conversations")
    claim: Mapped["ClaimModel"] = relationship(back_populates="claim_conversations")
    messages: Mapped[List["MessageModel"]] = relationship(
        back_populates="claim_conversation", cascade="all, delete-orphan"
    )


class MessageModel(Base):
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    sender_type: Mapped[MessageSenderType] = mapped_column(
        SQLEnum(MessageSenderType, name="message_sender_type"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    claim_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete='SET NULL'), nullable=True, index=True
    )
    analysis_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis.id", ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    claim_conversation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim_conversations.id" , ondelete='SET NULL'), nullable=True, index=True, 
    )

    conversation: Mapped["ConversationModel"] = relationship(back_populates="messages")
    claim: Mapped[Optional["ClaimModel"]] = relationship(back_populates="messages")
    analysis: Mapped[Optional["AnalysisModel"]] = relationship(back_populates="messages")
    claim_conversation: Mapped[Optional["ClaimConversationModel"]] = relationship(back_populates="messages")

    __table_args__ = (
        Index("idx_message_conversation_timestamp", conversation_id, timestamp.desc()),
        Index("idx_message_claim_conversation_timestamp", claim_conversation_id, timestamp.desc()),
    )
