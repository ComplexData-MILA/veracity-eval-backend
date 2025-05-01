import logging
from typing import AsyncGenerator, Dict, Any, List, Optional, NamedTuple
from uuid import UUID, uuid4
from datetime import UTC, datetime
import json
import re

from app.core.exceptions import NotAuthorizedException, NotFoundException, ValidationError
from app.core.llm.interfaces import LLMProvider
from app.models.database.models import AnalysisStatus, ClaimStatus, ConversationStatus, MessageSenderType
from app.models.domain.claim import Claim
from app.models.domain.analysis import Analysis
from app.models.domain.search import Search
from app.models.domain.message import Message
from app.core.llm.messages import Message as LLMMessage
from app.models.domain.conversation import Conversation
from app.models.domain.claim_conversation import ClaimConversation
from app.repositories.implementations.claim_conversation_repository import ClaimConversationRepository
from app.repositories.implementations.claim_repository import ClaimRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.message_repository import MessageRepository
from app.repositories.implementations.conversation_repository import ConversationRepository
from app.repositories.implementations.source_repository import SourceRepository
from app.repositories.implementations.search_repository import SearchRepository
from app.services.interfaces.web_search_service import WebSearchServiceInterface

from app.core.llm.prompts import AnalysisPrompt

logger = logging.getLogger(__name__)

MAX_NUM_TURNS: int = 10
MAX_SEARCH_RESULTS: int = 10


class _KeywordExtractionOutput(NamedTuple):
    """Represent the part up to the matched string, and the match itself."""

    content_up_to_match: str
    matched_content: str


class AnalysisState:
    def __init__(self):
        self.current_claim: Optional[Claim] = None
        self.current_analysis: Optional[Analysis] = None
        self.current_conversation: Optional[Conversation] = None
        self.current_claim_conversation: Optional[ClaimConversation] = None
        self.analysis_text: List[str] = []
        self.is_complete: bool = False


class AnalysisOrchestrator:
    def __init__(
        self,
        llm_provider: LLMProvider,
        claim_repo: ClaimRepository,
        analysis_repo: AnalysisRepository,
        conversation_repo: ConversationRepository,
        claim_conversation_repo: ClaimConversationRepository,
        message_repo: MessageRepository,
        source_repo: SourceRepository,
        search_repo: SearchRepository,
        web_search_service: WebSearchServiceInterface,
    ):
        self._llm = llm_provider
        self._claim_repo = claim_repo
        self._analysis_repo = analysis_repo
        self._conversation_repo = conversation_repo
        self._claim_conversation_repo = claim_conversation_repo
        self._message_repo = message_repo
        self._source_repo = source_repo
        self._search_repo = search_repo
        self._web_search = web_search_service
        self._analysis_state = AnalysisState()

    async def _generate_analysis(
        self, claim_text: str, context: str, language: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate analysis for a claim with web search and source management."""
        try:
            initial_analysis = Analysis(
                id=uuid4(),
                claim_id=self._analysis_state.current_claim.id,
                veracity_score=0.0,
                confidence_score=0.0,
                analysis_text="",
                status=AnalysisStatus.processing.value,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            current_analysis = await self._analysis_repo.create(initial_analysis)

            yield {"type": "status", "content": "Searching for relevant sources..."}

            query = self._query_initial(claim_text, language)
            messages = [LLMMessage(role="user", content=query)]
            all_sources = []
            for turns in range(MAX_NUM_TURNS):

                response = await self._llm.generate_response(messages)

                main_agent_message = response.text

                assert main_agent_message is not None, (
                    "Invalid Main Agent API response:",
                    response,
                )

                # If search is requested in a message, truncate that message
                # up to the search request. (Discard anything after the query.)

                search_request_match = self._extract_search_query_or_none(main_agent_message, language)
                if search_request_match is not None:
                    initial_search = Search(
                        id=uuid4(),
                        analysis_id=current_analysis.id,
                        prompt=search_request_match.matched_content,
                        summary=search_request_match.content_up_to_match,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                    current_search = await self._search_repo.create(initial_search)
                    sources = await self._web_search.search_and_create_sources(
                        claim_text=search_request_match.matched_content, search_id=current_search.id, language=language, option=[1]
                    )

                    all_sources += sources

                    search_response = self._web_search.format_sources_for_prompt(sources, language)

                    if language == "english":
                        messages += [
                            LLMMessage(role="assistant", content=main_agent_message),
                            LLMMessage(role="user", content=f"Search result: {search_response}"),
                        ]
                    elif language == "french":
                        messages += [
                            LLMMessage(role="assistant", content=main_agent_message),
                            LLMMessage(
                                role="user", content=f"Résultat(s) de la recherche sur le Web: {search_response}"
                            ),
                        ]
                    else:
                        raise ValidationError("Claim Language is invalid")

                    continue
                else:
                    messages += [LLMMessage(role="assistant", content=main_agent_message)]

                if (
                    main_agent_message.strip().lower().endswith("ready")
                    or main_agent_message.strip().lower().endswith("prêt")
                    or main_agent_message.strip().lower().endswith("prête")
                ):
                    break

            source_credibility = self._web_search.calculate_overall_credibility(all_sources)

            if not all_sources:
                yield {
                    "type": "status",
                    "content": "No reliable sources found. Proceeding with analysis based on claim content only.",
                }
            else:
                yield {
                    "type": "status",
                    "content": f"Found {len(sources)} relevant sources (overall credibility: {source_credibility:.2f})",
                }

            sources_text = self._web_search.format_sources_for_prompt(all_sources, language)
            logger.debug(f"Sources for all searches to be analyzed {sources_text}")
            yield {"type": "status", "content": "Analyzing claim with gathered sources..."}

            if language == "english":
                messages += [LLMMessage(role="user", content=AnalysisPrompt.GET_VERACITY)]
            elif language == "french":
                messages += [LLMMessage(role="user", content=AnalysisPrompt.GET_VERACITY_FR)]

            analysis_text = []
            logger.debug(messages)
            async for chunk in self._llm.generate_stream(messages):
                if not chunk.is_complete:
                    analysis_text.append(chunk.text)
                    yield {"type": "content", "content": chunk.text}
                else:
                    full_text = "".join(analysis_text)

                    try:
                        # Clean the text before parsing
                        # fmt: off
                        cleaned_text = (
                            full_text.strip()
                            .replace("\r", "")  # Remove carriage returns
                            .replace("\x00", "")  # Remove null bytes
                            .replace("\x1a", "")  # Remove SUB characters
                            .replace("\n", "")
                            .replace("\\\'", "'")
                            .replace("\t", "")
                        )
                        # fmt: on
                        # Try to find the JSON object if there's additional text
                        try:
                            start_idx = cleaned_text.find("{")
                            end_idx = cleaned_text.rindex("}") + 1
                            if start_idx != -1 and end_idx != -1:
                                cleaned_text = cleaned_text[start_idx:end_idx]
                        except ValueError:
                            pass

                        response_data = json.loads(cleaned_text)

                        logger.debug(response_data)

                        veracity_score = int(response_data.get("veracity_score", 0))
                        analysis_content = str(response_data.get("analysis", "No analysis provided"))

                        veracity_score = max(0, min(100, veracity_score))

                        current_analysis.veracity_score = float(veracity_score) / 100
                        current_analysis.analysis_text = analysis_content
                        current_analysis.status = AnalysisStatus.completed.value
                        current_analysis.updated_at = datetime.now(UTC)

                        updated_analysis = await self._analysis_repo.update(current_analysis)

                        yield {
                            "type": "analysis_complete",
                            "content": {
                                "analysis_id": str(updated_analysis.id),
                                "veracity_score": updated_analysis.veracity_score,
                                "num_sources": len(all_sources),
                                "source_credibility": source_credibility,
                            },
                        }

                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parsing error: {str(e)}\nFull text: {full_text}")
                        import re

                        try:
                            veracity_match = re.search(r'"veracity_score":\s*(0?\.\d+)', cleaned_text)
                            analysis_match = re.search(r'"analysis":\s*"([^"]+)"', cleaned_text)

                            if veracity_match and analysis_match:
                                veracity_score = int(veracity_match.group(1))
                                analysis_content = analysis_match.group(1)

                                current_analysis.veracity_score = float(veracity_score) / 100
                                current_analysis.analysis_text = analysis_content
                                current_analysis.status = AnalysisStatus.completed.value
                                current_analysis.updated_at = datetime.now(UTC)

                                updated_analysis = await self._analysis_repo.update(current_analysis)

                                yield {
                                    "type": "analysis_complete",
                                    "content": {
                                        "analysis_id": str(updated_analysis.id),
                                        "veracity_score": updated_analysis.veracity_score,
                                        "num_sources": len(all_sources),
                                        "source_credibility": source_credibility,
                                    },
                                }
                            else:
                                raise ValueError("Could not extract required fields using regex")

                        except Exception as regex_error:
                            logger.error(f"Regex fallback failed: {str(regex_error)}")
                            current_analysis.status = AnalysisStatus.failed.value
                            await self._analysis_repo.update(current_analysis)
                            yield {"type": "error", "content": f"Error parsing analysis response: {str(e)}"}
                            raise

                    except Exception as e:
                        logger.error(f"Error processing analysis: {str(e)}")
                        current_analysis.status = AnalysisStatus.failed.value
                        await self._analysis_repo.update(current_analysis)
                        yield {"type": "error", "content": f"Error creating analysis: {str(e)}"}
                        raise

        except Exception as e:
            logger.error(f"Error in _generate_analysis: {str(e)}", exc_info=True)
            yield {"type": "error", "content": str(e)}
            raise

    async def initialize_claim_conversation(
        self,
        user_id: UUID,
        claim_text: str,
        analysis_text: str,
        claim_id: UUID,
        analysis_id: UUID,
    ) -> Dict[str, UUID]:
        """Initialize conversation structure with claim and analysis."""
        try:
            # First create the main conversation
            conversation = Conversation(
                id=uuid4(),
                user_id=user_id,
                start_time=datetime.now(UTC),
                status=ConversationStatus.active,
            )
            conversation = await self._conversation_repo.create(conversation)
            self._analysis_state.current_conversation = conversation

            # Then create the claim conversation
            claim_conv = ClaimConversation(
                id=uuid4(),
                conversation_id=conversation.id,
                claim_id=claim_id,
                start_time=datetime.now(UTC),
                status=ConversationStatus.active,
            )
            claim_conv = await self._claim_conversation_repo.create(claim_conv)
            self._analysis_state.current_claim_conversation = claim_conv

            # Create initial claim message
            user_message = Message(
                id=uuid4(),
                conversation_id=conversation.id,
                claim_conversation_id=claim_conv.id,
                sender_type=MessageSenderType.user,
                content=claim_text,
                timestamp=datetime.now(UTC),
                claim_id=claim_id,
            )
            await self._message_repo.create(user_message)

            # Create analysis response message
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

            return {"conversation_id": conversation.id, "claim_conversation_id": claim_conv.id}
        except Exception as e:
            logger.error(f"Error initializing claim conversation: {str(e)}", exc_info=True)
            raise

    async def process_user_message(
        self, user_id: UUID, content: str, conversation_id: Optional[UUID] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a user message, potentially containing a claim to analyze"""
        try:
            conversation = await self._initialize_conversation(user_id, conversation_id)

            await self._store_user_message(conversation.id, content)

            has_claim = await self._detect_claim(content)

            if has_claim:
                async for chunk in self._handle_claim_message(user_id, conversation.id, content):
                    yield chunk
            else:
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
        # Might force this to return True
        response = await self._llm.generate_response([LLMMessage(role="user", content=prompt)])
        return response.text.strip().lower() == "true"

    async def _handle_claim_message(
        self, user_id: UUID, conversation_id: UUID, content: str, language: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handle message containing a claim"""
        claim_text = await self._extract_claim(content)

        claim = Claim(id=uuid4(), user_id=user_id, claim_text=claim_text, context=content, created_at=datetime.now())
        self._analysis_state.current_claim = await self._claim_repo.create(claim)

        claim_conversation = ClaimConversation(
            id=uuid4(), conversation_id=conversation_id, claim_id=claim.id, start_time=datetime.now()
        )
        # Create Claim Conversation does not exist, do I need to build out this method?
        await self._conversation_repo.create_claim_conversation(claim_conversation)

        yield {"type": "status", "content": "Analyzing claim..."}

        async for chunk in self._generate_analysis(claim_text, content, language):
            if chunk["type"] == "content":
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
        """Stream the analysis process for a claim and initialize conversation."""
        try:
            logger.info(f"Starting analysis for claim {claim_id}")

            claim = await self._claim_repo.get(claim_id)
            if not claim:
                raise ValueError(f"Claim {claim_id} not found")

            logger.debug(f"Retrieved claim: {claim.claim_text}")
            self._analysis_state.current_claim = claim

            await self._claim_repo.update_status(claim_id, ClaimStatus.analyzing)
            yield {"type": "status", "content": "Starting analysis..."}

            # Generate analysis
            analysis_complete = False
            async for chunk in self._generate_analysis(claim.claim_text, claim.context, claim.language):
                if chunk["type"] == "analysis_complete":
                    analysis_complete = True
                    # Get the full analysis to create conversation
                    analysis = await self._analysis_repo.get(UUID(chunk["content"]["analysis_id"]))

                    # Initialize conversation structure
                    conversation_ids = await self.initialize_claim_conversation(
                        user_id=user_id,
                        claim_text=claim.claim_text,
                        analysis_text=analysis.analysis_text,
                        claim_id=claim_id,
                        analysis_id=analysis.id,
                    )

                    # Add conversation IDs to the response
                    chunk["content"]["conversation_id"] = str(conversation_ids["conversation_id"])
                    chunk["content"]["claim_conversation_id"] = str(conversation_ids["claim_conversation_id"])

                yield chunk

            if analysis_complete:
                await self._claim_repo.update_status(claim_id, ClaimStatus.analyzed)
                logger.info(f"Completed analysis for claim {claim_id}")
            else:
                await self._claim_repo.update_status(claim_id, ClaimStatus.failed)
                logger.error(f"Analysis incomplete for claim {claim_id}")

        except Exception as e:
            logger.error(f"Error in analyze_claim_stream: {str(e)}", exc_info=True)
            if self._analysis_state.current_claim:
                await self._claim_repo.update_status(claim_id, ClaimStatus.rejected)
            yield {"type": "error", "content": str(e)}
            raise

    async def analyze_claim_direct(self, claim_id: UUID, user_id: UUID) -> Dict[str, Any]:
        claim = await self._claim_repo.get(claim_id)
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")

        self._analysis_state.current_claim = claim
        await self._claim_repo.update_status(claim_id, ClaimStatus.analyzing)

        analysis_complete = False
        final_chunk = None

        async for chunk in self._generate_analysis(claim.claim_text, claim.context, claim.language):
            if chunk["type"] == "analysis_complete":
                analysis_complete = True
                final_chunk = chunk

        if not analysis_complete:
            await self._claim_repo.update_status(claim_id, ClaimStatus.failed)
            raise ValueError(f"Analysis incomplete for claim {claim_id}")

        # Get analysis and initialize conversations
        analysis = await self._analysis_repo.get_with_relations(UUID(final_chunk["content"]["analysis_id"]))

        conversation_ids = await self.initialize_claim_conversation(
            user_id=user_id,
            claim_text=claim.claim_text,
            analysis_text=analysis.analysis_text,
            claim_id=claim_id,
            analysis_id=analysis.id,
        )

        await self._claim_repo.update_status(claim_id, ClaimStatus.analyzed)

        return {
            "conversation_id": conversation_ids["conversation_id"],
            "claim_conversation_id": conversation_ids["claim_conversation_id"],
            "analysis": analysis,
        }

    async def stream_claim_discussion(
        self,
        conversation_id: UUID,
        claim_conversation_id: UUID,
        claim_id: UUID,
        user_id: UUID,
        message_content: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream interactive discussion about a claim."""
        try:
            # First verify the conversation belongs to the user
            conversation = await self._conversation_repo.get(conversation_id)
            if not conversation or conversation.user_id != user_id:
                raise NotAuthorizedException("Not authorized to access this conversation")

            # Verify the claim conversation
            claim_conv = await self._claim_conversation_repo.get(claim_conversation_id)
            if not claim_conv or claim_conv.conversation_id != conversation_id:
                raise NotAuthorizedException("Not authorized to access this claim conversation")

            # Store user message
            user_message = Message(
                id=uuid4(),
                conversation_id=conversation_id,
                claim_conversation_id=claim_conversation_id,
                sender_type=MessageSenderType.user,
                content=message_content,
                timestamp=datetime.now(UTC),
                claim_id=claim_id,
            )
            await self._message_repo.create(user_message)

            # Get conversation context (last few messages for context)
            context_messages = await self._message_repo.get_claim_conversation_messages(
                claim_conversation_id=claim_conversation_id,
                limit=10,
            )
            context_messages.reverse()  # Oldest messages first

            # Create LLM messages from context
            llm_messages = [
                LLMMessage(
                    role="assistant" if msg.sender_type == MessageSenderType.bot else "user", content=msg.content
                )
                for msg in context_messages
            ]

            # Add current message
            llm_messages.append(LLMMessage(role="user", content=message_content))

            # Create bot message placeholder
            bot_message = Message(
                id=uuid4(),
                conversation_id=conversation_id,
                claim_conversation_id=claim_conversation_id,
                sender_type=MessageSenderType.bot,
                content="",
                timestamp=datetime.now(UTC),
                claim_id=claim_id,
            )
            await self._message_repo.create(bot_message)

            # Get claim and analysis for context
            claim = await self._claim_repo.get(claim_id)
            if not claim:
                raise NotFoundException("Claim not found")

            # Get latest analysis
            analyses = await self._analysis_repo.get_by_claim(claim_id=claim_id, include_sources=True)
            analysis = analyses[-1] if analyses else None

            if not analysis:
                raise NotFoundException("Analysis not found")

            system_context = (
                f"You are a fact-checking assistant. The user is asking about this claim: '{claim.claim_text}'\n"
                f"Your previous analysis determined this claim is {analysis.veracity_score * 100:.1f}% likely to be true "
                f"with {analysis.confidence_score * 100:.1f}% confidence.\n"
                "Please help the user understand the analysis and sources. "
                "Be direct and factual in your responses."
            )
            llm_messages.insert(0, LLMMessage(role="system", content=system_context))

            response_content = []
            async for chunk in self._llm.generate_stream(llm_messages, temperature=0.7):
                if not chunk.is_complete:
                    response_content.append(chunk.text)
                    yield {"type": "content", "content": chunk.text, "message_id": str(bot_message.id)}

                # Update bot message with complete response when done
                if chunk.is_complete:
                    full_response = "".join(response_content)
                    bot_message.content = full_response
                    await self._message_repo.update(bot_message)

                    yield {"type": "message_complete", "message_id": str(bot_message.id)}

        except Exception as e:
            logger.error(f"Error in stream_claim_discussion: {str(e)}", exc_info=True)
            yield {"type": "error", "content": str(e)}
            raise

    def clean_text(text):
        cleaned_text = re.sub(r"[^a-zA-Z,.?!' ]", "", text)
        return cleaned_text

    def _query_initial(self, statement: str, language: str):

        if language == "english":
            return AnalysisPrompt.ORCHESTRATOR_PROMPT.format(statement=statement, date=datetime.now().isoformat())
        elif language == "french":
            return AnalysisPrompt.ORCHESTRATOR_PROMPT_FR.format(statement=statement, date=datetime.now().isoformat())
        else:
            raise ValidationError("Claim Language is invalid")

    def _extract_search_query_or_none(
        self,
        assistant_response: str,
        language: str,
    ) -> Optional[_KeywordExtractionOutput]:
        """
        Try to extract "SEARCH: query\\n" request from the main agent response.

        Discards anything after the "query" part.

        Returns:
            _KeywordExtractionOutput if matched.
            None otherwise.
        """
        if language == "english":
            match = re.search(r"^\s*REASON:\s*(.*?)\s*SEARCH:\s+(.+)$", assistant_response, re.DOTALL | re.MULTILINE)
        elif language == "french":
            # TODO replace once French Prompt is settled
            match = re.search(
                r"^\s*REASON\s*:\s*(.*?)\s*SEARCH\s*:\s+(.+)$", assistant_response, re.DOTALL | re.MULTILINE
            )
        else:
            raise ValidationError("Claim Language is invalid")

        if match is None:
            return None
        return _KeywordExtractionOutput(
            content_up_to_match=match.group(1),
            matched_content=match.group(2),
        )

    def _extract_search_summary_or_none(
        self,
        assistant_response: str,
    ) -> Optional[_KeywordExtractionOutput]:
        """
        Try to extract "SEARCH: query\\n" request from the main agent response.

        Discards anything after the "query" part.

        Returns:
            _KeywordExtractionOutput if matched.
            None otherwise.
        """
        match = re.search(r"(.*?SUMMARY:\s+)(.+?)(\s*$)", assistant_response, re.DOTALL | re.MULTILINE)
        if match is None:
            return None
        return _KeywordExtractionOutput(
            content_up_to_match=match.group(1) + match.group(2),
            matched_content=match.group(2),
        )

    def _extract_prediction_or_none(self, assistant_response: str) -> Optional[str]:
        """
        Try to extract "Factuality: 0 to 1" from main agent response.

        Response:
            Prediction value (as a string) if matched.
            None otherwise.
        """

        match = re.search(r"READY", assistant_response)
        if match is None:
            return None

        return match.group(1)
