import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import UTC, datetime
import json

from app.core.llm.interfaces import LLMProvider
from app.models.database.models import AnalysisStatus, ClaimStatus
from app.models.domain.claim import Claim
from app.models.domain.analysis import Analysis
from app.models.domain.message import Message
from app.core.llm.messages import Message as LLMMessage
from app.models.domain.conversation import Conversation
from app.models.domain.claim_conversation import ClaimConversation
from app.repositories.implementations.claim_repository import ClaimRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.message_repository import MessageRepository
from app.repositories.implementations.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


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

    async def _generate_analysis(self, claim_text: str, context: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate analysis for a claim with improved streaming."""
        prompt = (
            "Analyze the following claim and provide:\n"
            "1. A veracity score (0-1)\n"
            "2. A confidence score (0-1)\n"
            "3. A detailed analysis\n\n"
            f"Claim: {claim_text}\n"
            f"Context: {context}"
        )

        yield {"type": "status", "content": "Analyzing claim content..."}

        analysis_text = []
        async for chunk in self._llm.generate_stream([LLMMessage(role="user", content=prompt)]):
            if not chunk.is_complete:
                analysis_text.append(chunk.text)
                yield {"type": "content", "content": chunk.text}
            else:
                # Create analysis record
                full_text = "".join(analysis_text)

                try:
                    # Extract scores
                    scores_prompt = (
                        "Extract the veracity and confidence scores from this analysis. "
                        "Respond with only a JSON object containing 'veracity_score' and "
                        "'confidence_score':\n\n"
                        f"{full_text}"
                    )
                    scores_response = await self._llm.generate_response(
                        [LLMMessage(role="user", content=scores_prompt)]
                    )
                    scores = json.loads(scores_response.text)

                    # Create the analysis
                    analysis = Analysis(
                        id=uuid4(),
                        claim_id=self._analysis_state.current_claim.id,
                        veracity_score=float(scores["veracity_score"]),
                        confidence_score=float(scores["confidence_score"]),
                        analysis_text=full_text,
                        status=AnalysisStatus.COMPLETED.value,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )

                    created_analysis = await self._analysis_repo.create(analysis)
                    self._analysis_state.current_analysis = created_analysis

                    yield {
                        "type": "analysis_complete",
                        "content": {
                            "analysis_id": str(created_analysis.id),
                            "veracity_score": created_analysis.veracity_score,
                            "confidence_score": created_analysis.confidence_score,
                        },
                    }

                except Exception as e:
                    yield {"type": "error", "content": f"Error creating analysis: {str(e)}"}
                    raise

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

    async def analyze_claim_stream(self, claim_id: UUID, user_id: UUID) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream the analysis process for a claim."""
        try:
            logger.info(f"Starting analysis for claim {claim_id}")

            # Get the claim
            claim = await self._claim_repo.get(claim_id)
            if not claim:
                raise ValueError(f"Claim {claim_id} not found")

            logger.debug(f"Retrieved claim: {claim.claim_text}")

            # Update state
            self._analysis_state.current_claim = claim

            # Update claim status to analyzing
            await self._claim_repo.update_status(claim_id, ClaimStatus.analyzing)

            yield {"type": "status", "content": "Starting analysis..."}

            # Detect if it's a verifiable claim
            is_verifiable = await self._detect_claim(claim.claim_text)
            logger.debug(f"Claim verifiable check result: {is_verifiable}")

            if not is_verifiable:
                yield {"type": "status", "content": "This doesn't appear to be a verifiable claim."}
                await self._claim_repo.update_status(claim_id, ClaimStatus.rejected)
                return

            # Generate analysis
            logger.debug("Starting analysis generation")
            async for chunk in self._generate_analysis(claim.claim_text, claim.context):
                yield chunk

            # Update claim status to analyzed
            await self._claim_repo.update_status(claim_id, ClaimStatus.analyzed)

            logger.info(f"Completed analysis for claim {claim_id}")

        except Exception as e:
            logger.error(f"Error in analyze_claim_stream: {str(e)}", exc_info=True)
            # Update claim status to failed if there's an error
            if self._analysis_state.current_claim:
                await self._claim_repo.update_status(claim_id, ClaimStatus.rejected)
            yield {"type": "error", "content": str(e)}
            raise
