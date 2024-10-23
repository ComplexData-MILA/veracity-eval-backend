# import uuid
# from sqlalchemy import CheckConstraint, String, Text, Float, ForeignKey
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from sqlalchemy.dialects.postgresql import UUID
# from datetime import UTC, datetime
# from typing import List, Optional
# import enum

# from app.models.database.base import Base


# class MessageType(enum.Enum):
#     USER = "user"
#     BOT = "bot"


# class ClaimModel(Base):
#     __tablename__ = "claims"

#     id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
#     claim_text: Mapped[str] = mapped_column(Text)
#     context: Mapped[str] = mapped_column(Text)

#     # Relationships
#     analysis: Mapped[List["AnalysisModel"]] = relationship(back_populates="claim")
#     messages: Mapped[List["MessageModel"]] = relationship(back_populates="claim")
#     claim_conversations: Mapped[List["ClaimConversationModel"]] = relationship(back_populates="claim")


# class AnalysisModel(Base):
#     __tablename__ = "analysis"

#     id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     claim_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
#     veracity_score: Mapped[float] = mapped_column(Float)
#     confidence_score: Mapped[float] = mapped_column(Float)
#     analysis_text: Mapped[str] = mapped_column(Text)

#     # Relationships
#     claim: Mapped["ClaimModel"] = relationship(back_populates="analysis")
#     sources: Mapped[List["SourceModel"]] = relationship(back_populates="analysis")
#     feedback: Mapped[List["FeedbackModel"]] = relationship(back_populates="analysis")
#     messages: Mapped[List["MessageModel"]] = relationship(back_populates="analysis")


# class MessageModel(Base):
#     __tablename__ = "messages"

#     id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     conversation_id: Mapped[Optional[UUID]] = mapped_column(
#         UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
#     )
#     claim_conversation_id: Mapped[Optional[UUID]] = mapped_column(
#         UUID(as_uuid=True), ForeignKey("claim_conversations.id"), nullable=True
#     )
#     sender_type: Mapped[str] = mapped_column(String, nullable=False)
#     content: Mapped[str] = mapped_column(Text)
#     claim_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=True)
#     analysis_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis.id"), nullable=True)

#     # Relationships
#     conversation: Mapped[Optional["ConversationModel"]] = relationship(back_populates="messages")
#     claim_conversation: Mapped[Optional["ClaimConversationModel"]] = relationship(back_populates="messages")
#     claim: Mapped[Optional["ClaimModel"]] = relationship(back_populates="messages")
#     analysis: Mapped[Optional["AnalysisModel"]] = relationship(back_populates="messages")


# class ConversationModel(Base):
#     __tablename__ = "conversations"

#     id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
#     start_time: Mapped[datetime] = mapped_column(default=datetime.now(UTC))
#     end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
#     status: Mapped[str] = mapped_column(String, default="active")

#     # Relationships
#     messages: Mapped[List["MessageModel"]] = relationship(back_populates="conversation")
#     claim_conversations: Mapped[List["ClaimConversationModel"]] = relationship(back_populates="conversation")
#     user: Mapped["UserModel"] = relationship(back_populates="conversations")


# class ClaimConversationModel(Base):
#     __tablename__ = "claim_conversations"

#     id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     conversation_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
#     claim_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
#     start_time: Mapped[datetime] = mapped_column(default=datetime.now(UTC))
#     end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
#     status: Mapped[str] = mapped_column(String, default="active")

#     # Relationships
#     conversation: Mapped["ConversationModel"] = relationship(back_populates="claim_conversations")
#     claim: Mapped["ClaimModel"] = relationship(back_populates="claim_conversations")
#     messages: Mapped[List["MessageModel"]] = relationship(back_populates="claim_conversation")


# class SourceModel(Base):
#     __tablename__ = "sources"

#     id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     analysis_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis.id"))
#     url: Mapped[str] = mapped_column(String)
#     title: Mapped[str] = mapped_column(String)
#     snippet: Mapped[str] = mapped_column(Text)
#     credibility_score: Mapped[float] = mapped_column(Float)

#     # Relationships
#     analysis: Mapped["AnalysisModel"] = relationship(back_populates="sources")


# class FeedbackModel(Base):
#     __tablename__ = "feedback"

#     id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     analysis_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis.id"))
#     user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
#     rating: Mapped[float] = mapped_column(Float)
#     comment: Mapped[str] = mapped_column(Text)

#     # Relationships
#     analysis: Mapped["AnalysisModel"] = relationship(back_populates="feedback")
#     user: Mapped["UserModel"] = relationship(back_populates="feedback")

#     __table_args__ = (CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),)
