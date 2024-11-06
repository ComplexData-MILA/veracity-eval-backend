from datetime import UTC, datetime
from typing import AsyncGenerator, Dict, Any, List
from uuid import UUID, uuid4
import logging

from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message as LLMMessage
from app.models.domain.message import Message
from app.models.domain.conversation import Conversation
from app.models.domain.claim_conversation import ClaimConversation
from app.models.database.models import MessageSenderType, ConversationStatus
from app.repositories.implementations.conversation_repository import ConversationRepository
from app.repositories.implementations.claim_conversation_repository import ClaimConversationRepository
from app.repositories.implementations.message_repository import MessageRepository

logger = logging.getLogger(__name__)


class ConversationStreamService:
    def __init__(
        self,
        llm_provider: LLMProvider,
        conversation_repo: ConversationRepository,
        claim_conversation_repo: ClaimConversationRepository,
        message_repo: MessageRepository,
    ):
        self._llm = llm_provider
        self._conversation_repo = conversation_repo
        self._claim_conversation_repo = claim_conversation_repo
        self._message_repo = message_repo

    async def initialize_claim_conversation(
        self,
        user_id: UUID,
        claim_text: str,
        analysis_text: str,
        claim_id: UUID,
        analysis_id: UUID,
    ) -> Dict[str, UUID]:
        """Initialize a new conversation with claim and analysis messages."""
        conversation = Conversation(
            id=uuid4(),
            user_id=user_id,
            start_time=datetime.now(UTC),
            status=ConversationStatus.active,
        )
        conversation = await self._conversation_repo.create(conversation)

        claim_conv = ClaimConversation(
            id=uuid4(),
            conversation_id=conversation.id,
            claim_id=claim_id,
            start_time=datetime.now(UTC),
            status=ConversationStatus.active,
        )
        claim_conv = await self._claim_conversation_repo.create(claim_conv)

        claim_message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            claim_conversation_id=claim_conv.id,
            sender_type=MessageSenderType.user,
            content=claim_text,
            timestamp=datetime.now(UTC),
            claim_id=claim_id,
        )
        await self._message_repo.create(claim_message)

        analysis_message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            claim_conversation_id=claim_conv.id,
            sender_type=MessageSenderType.bot,
            content=analysis_text,
            timestamp=datetime.now(UTC),
            claim_id=claim_id,
            analysis_id=analysis_id,
        )
        await self._message_repo.create(analysis_message)

        return {
            "conversation_id": conversation.id,
            "claim_conversation_id": claim_conv.id,
        }

    async def stream_interactive_response(
        self,
        user_message: str,
        conversation_id: UUID,
        claim_conversation_id: UUID,
        claim_id: UUID,
        user_id: UUID,
        context: List[Message] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream an interactive response in the claim conversation context."""
        try:
            user_msg = Message(
                id=uuid4(),
                conversation_id=conversation_id,
                claim_conversation_id=claim_conversation_id,
                sender_type=MessageSenderType.user,
                content=user_message,
                timestamp=datetime.now(UTC),
                claim_id=claim_id,
            )
            await self._message_repo.create(user_msg)

            messages = []
            if context:
                for msg in context:
                    role = "assistant" if msg.sender_type == MessageSenderType.bot else "user"
                    messages.append(LLMMessage(role=role, content=msg.content))

            # Add current message
            messages.append(LLMMessage(role="user", content=user_message))

            bot_msg = Message(
                id=uuid4(),
                conversation_id=conversation_id,
                claim_conversation_id=claim_conversation_id,
                sender_type=MessageSenderType.bot,
                content="",
                timestamp=datetime.now(UTC),
                claim_id=claim_id,
            )
            bot_msg = await self._message_repo.create(bot_msg)

            response_content = []
            async for chunk in self._llm.generate_stream(messages):
                if not chunk.is_complete:
                    response_content.append(chunk.text)
                    yield {
                        "type": "content",
                        "content": chunk.text,
                        "message_id": str(bot_msg.id),
                    }

            bot_msg.content = "".join(response_content)
            await self._message_repo.update(bot_msg)

            yield {
                "type": "message_complete",
                "message_id": str(bot_msg.id),
            }

        except Exception as e:
            logger.error(f"Error in stream_interactive_response: {str(e)}", exc_info=True)
            yield {"type": "error", "content": str(e)}
