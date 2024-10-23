from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from app.models.domain.conversation import Conversation
from app.models.database.models.conversation import ConversationStatus


class ConversationRepositoryInterface(ABC):
    """Interface for conversation repository operations."""

    @abstractmethod
    async def create(self, conversation: Conversation) -> Conversation:
        """Create a new conversation."""
        pass

    @abstractmethod
    async def get(self, conversation_id: UUID) -> Optional[Conversation]:
        """Get conversation by ID."""
        pass

    @abstractmethod
    async def get_user_conversations(
        self, user_id: UUID, status: Optional[ConversationStatus] = None
    ) -> List[Conversation]:
        """Get all conversations for a user."""
        pass

    @abstractmethod
    async def update_status(self, conversation_id: UUID, status: ConversationStatus) -> Optional[Conversation]:
        """Update conversation status."""
        pass

    @abstractmethod
    async def end_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        """End a conversation."""
        pass
