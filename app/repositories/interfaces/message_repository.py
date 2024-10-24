from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.domain.message import Message


class MessageRepositoryInterface(ABC):
    """Interface for message repository operations."""

    @abstractmethod
    async def create(self, message: Message) -> Message:
        """Create a new message."""
        pass

    @abstractmethod
    async def get(self, message_id: UUID) -> Optional[Message]:
        """Get message by ID."""
        pass

    @abstractmethod
    async def get_conversation_messages(
        self, conversation_id: UUID, before: Optional[datetime] = None, limit: int = 50
    ) -> List[Message]:
        """Get messages for a conversation with pagination."""
        pass

    @abstractmethod
    async def get_claim_conversation_messages(
        self, claim_conversation_id: UUID, before: Optional[datetime] = None, limit: int = 50
    ) -> List[Message]:
        """Get messages for a claim conversation with pagination."""
        pass

    @abstractmethod
    async def get_user_messages(
        self, user_id: UUID, before: Optional[datetime] = None, limit: int = 50
    ) -> List[Message]:
        """Get messages for a user with pagination."""
        pass
