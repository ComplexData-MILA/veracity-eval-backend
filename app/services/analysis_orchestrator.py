from typing import AsyncGenerator, Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime
import json

from app.core.llm.interfaces import LLMProvider
from app.core.llm.protocols import LLMMessage
from app.models.domain.claim import Claim
from app.models.domain.analysis import Analysis
from app.models.domain.message import Message
from app.models.domain.conversation import Conversation
from app.models.domain.claim_conversation import ClaimConversation
from app.repositories.implementations.claim_repository import ClaimRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.message_repository import MessageRepository
from app.repositories.implementations.conversation_repository import ConversationRepository


class AnalysisState:
    def __init__(self):
        self.current_claim: Optional[Claim] = None
        self.current_analysis: Optional[Analysis] = None
        self.analysis_text: List[str] = []
        self.is_complete: bool = False


class AnalysisOrchestrator:
    def __init__(
        self,
        llm_provider: LLMProvider,
        claim_repo: ClaimRepository,
        analysis_repo: AnalysisRepository,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
    ):
        self._llm = llm_provider
        self._claim_repo = claim_repo
        self._analysis_repo = analysis_repo
        self._conversation_repo = conversation_repo
        self._message_repo = message_repo
        self._analysis_state = AnalysisState()

    async def process_user_message(
        self, user_id: UUID, content: str, conversation_id: Optional[UUID] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a user message, potentially containing a claim to analyze"""
        try:
            # Initialize or get conversation
            conversation = await self._initialize_conversation(user_id, conversation_id)

            # Store user message
            await self._store_user_message(conversation.id, content)

            # Detect if message contains a claim
            has_claim = await self._detect_claim(content)

            if has_claim:
                # Process as claim
                async for chunk in self._handle_claim_message(user_id, conversation.id, content):
                    yield chunk
            else:
                # Process as regular conversation
                async for chunk in self._handle_regular_message(conversation.id, content):
                    yield chunk

        except Exception as e:
            yield {"type": "error", "content": f"Error processing message: {str(e)}"}

    async def _initialize_conversation(self, user_id: UUID, conversation_id: Optional[UUID]) -> Conversation:
        """Initialize or retrieve conversation"""
        if conversation_id:
            conversation = await self._conversation_repo.get(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
            return conversation

        conversation = Conversation(id=uuid4(), user_id=user_id, start_time=datetime.now())
        return await self._conversation_repo.create(conversation)

    async def _store_user_message(self, conversation_id: UUID, content: str) -> Message:
        """Store user message in the database"""
        message = Message(
            id=uuid4(), conversation_id=conversation_id, sender_type="user", content=content, timestamp=datetime.now()
        )
        return await self._message_repo.create(message)

    async def _detect_claim(self, content: str) -> bool:
        """Detect if message contains a claim using LLM"""
        prompt = (
            "Determine if the following message contains a verifiable claim that "
            "could be fact-checked. Respond with 'true' or 'false':\n\n"
            f"Message: {content}"
        )
        response = await self._llm.generate_response([LLMMessage(role="user", content=prompt)])
        return response.text.strip().lower() == "true"

    async def _handle_claim_message(
        self, user_id: UUID, conversation_id: UUID, content: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handle message containing a claim"""
        # Extract claim
        claim_text = await self._extract_claim(content)

        # Create claim record
        claim = Claim(id=uuid4(), user_id=user_id, claim_text=claim_text, context=content, created_at=datetime.now())
        self._analysis_state.current_claim = await self._claim_repo.create(claim)

        # Create claim conversation
        claim_conversation = ClaimConversation(
            id=uuid4(), conversation_id=conversation_id, claim_id=claim.id, start_time=datetime.now()
        )
        await self._conversation_repo.create_claim_conversation(claim_conversation)

        yield {"type": "status", "content": "Analyzing claim..."}

        # Generate analysis
        async for chunk in self._generate_analysis(claim_text, content):
            if chunk["type"] == "content":
                # Store bot message
                await self._store_bot_message(
                    conversation_id=conversation_id, content=chunk["content"], claim_id=claim.id
                )
            yield chunk

    async def _extract_claim(self, content: str) -> str:
        """Extract the main claim from message content"""
        prompt = (
            "Extract the main verifiable claim from the following message. "
            "Return only the claim, nothing else:\n\n"
            f"Message: {content}"
        )
        response = await self._llm.generate_response([LLMMessage(role="user", content=prompt)])
        return response.text.strip()

    async def _generate_analysis(self, claim_text: str, context: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate analysis for a claim"""
        prompt = (
            "Analyze the following claim and provide:\n"
            "1. A veracity score (0-1)\n"
            "2. A confidence score (0-1)\n"
            "3. A detailed analysis\n\n"
            f"Claim: {claim_text}\n"
            f"Context: {context}"
        )

        analysis_text = []
        async for chunk in self._llm.generate_stream([LLMMessage(role="user", content=prompt)]):
            if not chunk.is_complete:
                analysis_text.append(chunk.text)
                yield {"type": "content", "content": chunk.text}
            else:
                # Create analysis record
                full_text = "".join(analysis_text)
                analysis = await self._create_analysis(full_text, self._analysis_state.current_claim.id)

                yield {
                    "type": "analysis_complete",
                    "content": {
                        "analysis_id": str(analysis.id),
                        "veracity_score": analysis.veracity_score,
                        "confidence_score": analysis.confidence_score,
                    },
                }

    async def _create_analysis(self, analysis_text: str, claim_id: UUID) -> Analysis:
        """Create analysis record from generated text"""
        # Extract scores using LLM
        scores_prompt = (
            "Extract the veracity and confidence scores from this analysis. "
            "Respond with only a JSON object containing 'veracity_score' and "
            "'confidence_score':\n\n"
            f"{analysis_text}"
        )
        scores_response = await self._llm.generate_response([LLMMessage(role="user", content=scores_prompt)])
        scores = json.loads(scores_response.text)

        analysis = Analysis(
            id=uuid4(),
            claim_id=claim_id,
            veracity_score=float(scores["veracity_score"]),
            confidence_score=float(scores["confidence_score"]),
            analysis_text=analysis_text,
            created_at=datetime.now(),
        )
        return await self._analysis_repo.create(analysis)

    async def _handle_regular_message(
        self, conversation_id: UUID, content: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handle regular conversational message"""
        async for chunk in self._llm.generate_stream([LLMMessage(role="user", content=content)]):
            if not chunk.is_complete:
                await self._store_bot_message(conversation_id, chunk.text)
                yield {"type": "content", "content": chunk.text}

    async def _store_bot_message(self, conversation_id: UUID, content: str, claim_id: Optional[UUID] = None) -> Message:
        """Store bot message in the database"""
        message = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            sender_type="bot",
            content=content,
            timestamp=datetime.now(),
            claim_id=claim_id,
        )
        return await self._message_repo.create(message)
