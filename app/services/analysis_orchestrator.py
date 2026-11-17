import asyncio
import json
import logging
import math
import re
import secrets
import time
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, AsyncGenerator, Dict, List, NamedTuple, Optional
from uuid import UUID, uuid4

from app.core.config import settings
from app.core.exceptions import NotAuthorizedException, NotFoundException, ValidationError
from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message as LLMMessage
from app.core.llm.prompts import AnalysisPrompt
from app.core.text_safety import (
    clean_unicode_text,
    extract_json_candidate,
    flatten_untrusted,
    looks_like_injection,
    parse_analysis_response,
    wrap_untrusted,
)
from app.models.database.models import (
    AnalysisStatus,
    ClaimStatus,
    ConversationStatus,
    MessageSenderType,
    SourceModel,
)
from app.models.domain.analysis import Analysis, LogProbsData
from app.models.domain.claim import Claim
from app.models.domain.claim_conversation import ClaimConversation
from app.models.domain.conversation import Conversation
from app.models.domain.message import Message
from app.models.domain.search import Search
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.claim_conversation_repository import ClaimConversationRepository
from app.repositories.implementations.claim_repository import ClaimRepository
from app.repositories.implementations.conversation_repository import ConversationRepository
from app.repositories.implementations.message_repository import MessageRepository
from app.repositories.implementations.search_repository import SearchRepository
from app.repositories.implementations.source_repository import SourceRepository
from app.services.interfaces.web_search_service import WebSearchServiceInterface
from app.services import claim_decomposition
from app.services.claim_extraction_service import take_planned_turn
from app.services.claim_matching import TIER_FULL
from app.services.harm_screen import screen_text
from app.services.semantic_cache_service import (
    CacheHit,
    CachePolicy,
    SemanticCacheService,
    SubclaimHit,
    split_for_replay,
)

logger = logging.getLogger(__name__)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

warning_handler = logging.FileHandler("exta_info.log")
warning_handler.setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
warning_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(warning_handler)
logger.propagate = False

MAX_NUM_TURNS: int = 10
MAX_SEARCH_RESULTS: int = 10

# Follow-up chat actions. Searches made from the chat are tagged so they are never replayed as cached verdict evidence.
FOLLOWUP_ANSWER = "answer"
FOLLOWUP_SEARCH = "search"
FOLLOWUP_RECHECK = "recheck"
FOLLOWUP_SEARCH_SUMMARY = "followup"
# Searches run for one decomposed subclaim, before the planner loop
SUBCLAIM_SEARCH_SUMMARY = "subclaim"
FOLLOWUP_REFUSAL = "Sorry, I can't help with that. I can help you understand this fact-check."
STREAM_ERROR = "Sorry, something went wrong. Please try again."
CONTENT_FILTER_REASONS = ("content_filter", "content_filtered")
# Characters held back at the start of a reply, until it is known not to be a leak or a block.
REPLY_HOLD_CHARS = 48
MIN_REPLY_CHARS = 5


async def _single_reply(text: str) -> AsyncGenerator[str, None]:
    yield text


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _add_elapsed(timings: Dict[str, int], stage: str, start: float) -> None:
    """Accumulate a stage that runs more than once, e.g. one LLM call per search turn."""
    timings[stage] = timings.get(stage, 0) + _elapsed_ms(start)


def parse_followup_route(raw_text: str) -> tuple[str, str]:
    """Return (action, argument), where the argument is the search query or the revised claim.

    Anything unusable falls back to answering from the existing evidence.
    """
    try:
        data = json.loads(extract_json_candidate(raw_text))
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning(f"Malformed follow-up router JSON, answering from existing evidence. Raw={raw_text[:500]!r}")
        return FOLLOWUP_ANSWER, ""
    if not isinstance(data, dict):
        return FOLLOWUP_ANSWER, ""

    action = str(data.get("action", "")).strip().lower()
    argument = {FOLLOWUP_SEARCH: data.get("query"), FOLLOWUP_RECHECK: data.get("claim")}.get(action)
    argument = clean_unicode_text(argument).strip() if isinstance(argument, str) else ""
    if not argument:
        return FOLLOWUP_ANSWER, ""
    return action, argument[:500]


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
        semantic_cache: Optional[SemanticCacheService] = None,
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
        self._cache = semantic_cache
        self._analysis_state = AnalysisState()

    async def _generate_analysis(
        self,
        claim_text: str,
        context: str,
        language: str,
        default: bool = True,
        preferred_domains: list[str] | None = None,
        cache_policy: CachePolicy | None = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate analysis for a claim with web search and source management."""
        started = time.perf_counter()
        # Per-stage durations, sent with analysis_complete for latency benchmarks
        timings: Dict[str, int] = {}
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

            await self._analysis_repo._session.commit()
            timings["setup"] = _elapsed_ms(started)

            # Every route to a check passes here (clarifier fallbacks, direct API calls, batch, follow-up rechecks),
            # so the screen runs before any search, cached verdict or cache write. It runs even when the clarifier
            # passed the claim: the clarifier let through requests disguised as claims, and answers can add them.
            if settings.HARM_CHECK_ENABLED:
                stage = time.perf_counter()
                harmful = await self._is_harmful_request(claim_text)
                timings["harm_check"] = _elapsed_ms(stage)
                if harmful:
                    logger.warning(f"Check refused as a request for harmful help: claim {current_analysis.claim_id}")
                    refusal = (
                        AnalysisPrompt.CLARIFY_HARMFUL_REFUSAL_FR
                        if language == "french"
                        else AnalysisPrompt.CLARIFY_HARMFUL_REFUSAL
                    )
                    current_analysis.status = AnalysisStatus.failed.value
                    current_analysis.analysis_text = refusal
                    await self._analysis_repo.update(current_analysis)
                    yield {"type": "error", "content": refusal}
                    return

            yield {"type": "status", "content": "Searching for relevant sources..."}

            query = self._query_initial(claim_text, language)
            messages = [LLMMessage(role="user", content=query)]
            all_sources = []

            cache_key = self._cache.params_hash(language, default, preferred_domains) if self._cache else None
            cache_embedding, cache_hit = await self._cache_lookup(
                claim_text, language, cache_key, cache_policy, timings
            )
            cache_hit, all_sources = await self._claim_cache_hit(cache_hit, current_analysis.id, timings)
            if cache_hit and cache_hit.tier == TIER_FULL:
                async for event in self._replay_cached_analysis(
                    current_analysis, cache_hit, all_sources, timings, started
                ):
                    yield event
                return
            if cache_hit:
                # Evidence tier: skip the search loop and give the verdict step the cached sources
                messages = self._cached_evidence_messages(query, language, all_sources)

            subclaims, subclaim_entries = None, []
            if settings.CLAIM_DECOMPOSITION_ENABLED and not cache_hit:
                # Atomic subclaims, each with its own (possibly cached) search; the planner can still search more
                subclaims, messages, all_sources, subclaim_entries = await self._subclaim_evidence(
                    claim_text, query, language, current_analysis.id, preferred_domains, cache_policy, timings
                )

            # Turn 1 already planned by this user's combined clarify call; only used when turn 1 would see just the claim
            user_id = getattr(self._analysis_state.current_claim, "user_id", None)
            planned_turn = (
                take_planned_turn(claim_text, language, user_id) if settings.USE_COMBINED_MULTI_PROMPT else None
            )
            if not (len(messages) == 1 and messages[0].content == query):
                planned_turn = None

            stage = time.perf_counter()
            timings["llm_turns"] = timings["searches"] = 0
            for turns in range(0 if cache_hit else MAX_NUM_TURNS):

                await self._analysis_repo._session.rollback()

                if planned_turn is not None:
                    main_agent_message, planned_turn = planned_turn, None
                    timings["planned_turn"] = 1
                else:
                    turn_start = time.perf_counter()
                    response = await self._llm.generate_response(messages)
                    _add_elapsed(timings, "planner_llm", turn_start)
                    timings["llm_turns"] += 1

                    main_agent_message = response.text

                assert main_agent_message is not None, (
                    "Invalid Main Agent API response:",
                    response,
                )

                # If search is requested in a message, truncate that message
                # up to the search request. (Discard anything after the query.)

                search_request_match = self._extract_search_query_or_none(main_agent_message, language)
                if search_request_match is not None:
                    search_start = time.perf_counter()
                    initial_search = Search(
                        id=uuid4(),
                        analysis_id=current_analysis.id,
                        prompt=search_request_match.matched_content,
                        summary=search_request_match.content_up_to_match,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                    current_search = await self._search_repo.create(initial_search)

                    await self._search_repo._session.commit()

                    sources = await self._web_search.search_and_create_sources(
                        claim_text=search_request_match.matched_content,
                        search_id=current_search.id,
                        language=language,
                        preferred_domains=preferred_domains,
                    )

                    all_sources += sources
                    timings["searches"] += 1
                    # Provider call plus saving the sources; logged separately as "Web search timings" / "Web search sources"
                    _add_elapsed(timings, "web_search", search_start)

                    await self._analysis_repo._session.rollback()

                    search_response = self._evidence_prompt(sources, language)

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
                        current_analysis.status = AnalysisStatus.failed.value
                        updated_analysis = await self._analysis_repo.update(current_analysis)
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
            timings["search_loop"] = _elapsed_ms(stage)
            if preferred_domains and not all_sources:
                current_analysis.status = AnalysisStatus.failed.value
                current_analysis.analysis_text = (
                    "No usable evidence was retrieved from the selected "
                    "domains. This does not establish whether the claim "
                    "is true or false."
                )
                current_analysis.updated_at = datetime.now(UTC)

                await self._analysis_repo.update_stream_safe(current_analysis)

                yield {
                    "type": "insufficient_evidence",
                    "content": {
                        "analysis_id": str(current_analysis.id),
                        "message": current_analysis.analysis_text,
                        "preferred_domains": preferred_domains,
                        "can_expand_search": True,
                    },
                }
                return

            source_credibility = self._web_search.calculate_overall_credibility(all_sources)

            if not all_sources:
                yield {
                    "type": "status",
                    "content": "No reliable sources found. Proceeding with analysis based on claim content only.",
                }
            else:
                yield {
                    "type": "status",
                    "content": f"Found {len(all_sources)} relevant sources (overall credibility: {source_credibility:.2f})",
                }

            sources_text = self._web_search.format_sources_for_prompt(all_sources, language)
            logger.debug(f"Sources for all searches to be analyzed {sources_text}")
            yield {"type": "status", "content": "Analyzing claim with gathered sources..."}

            if language == "english":
                prompt = AnalysisPrompt.GET_VERACITY_EX if not default else AnalysisPrompt.GET_VERACITY
                messages += [LLMMessage(role="user", content=prompt + self._subclaim_rules(subclaims, language))]
            elif language == "french":
                messages += [
                    LLMMessage(
                        role="user", content=AnalysisPrompt.GET_VERACITY_FR + self._subclaim_rules(subclaims, language)
                    )
                ]

            analysis_text = []
            log_probs = []

            await self._analysis_repo._session.rollback()

            verdict_temperature = settings.SEMCACHE_VERDICT_TEMPERATURE if cache_hit else 0.7
            stage = time.perf_counter()
            async for chunk in self._llm.generate_stream(messages, temperature=verdict_temperature):
                timings.setdefault("verdict_ttft", _elapsed_ms(stage))
                if not chunk.is_complete:
                    analysis_text.append(chunk.text)
                    log_probs.append(chunk.metadata.get("logprobs"))
                    yield {"type": "content", "content": chunk.text}
                else:
                    full_text = "".join(analysis_text)
                    timings["verdict"] = _elapsed_ms(stage)
                    # logger.warning(f"length {len(analysis_text)}, {analysis_text}")
                    # logger.warning(f"length {len(log_probs)}, {log_probs}")

                    try:
                        # OLD VERSION KEPT FOR REFERENCE:
                        # Clean the text before parsing
                        # fmt: off
                        # cleaned_text = (
                        #    full_text.strip()
                        #    .replace("\r", "")  # Remove carriage returns
                        #    .replace("\x00", "")  # Remove null bytes
                        #    .replace("\x1a", "")  # Remove SUB characters
                        #    .replace("\n", "")
                        #    .replace("\\\'", "'")
                        #    .replace("\t", "")
                        # )
                        # fmt: on
                        # Try to find the JSON object if there's additional text
                        # try:
                        #    start_idx = cleaned_text.find("{")
                        #    end_idx = cleaned_text.rindex("}") + 1
                        #    if start_idx != -1 and end_idx != -1:
                        #        cleaned_text = cleaned_text[start_idx:end_idx]
                        # except ValueError:
                        # pass

                        # response_data = json.loads(cleaned_text)

                        # logger.debug(response_data)

                        # veracity_score = int(response_data.get("veracity_score", 0))
                        # analysis_content = str(response_data.get("analysis", "No analysis provided"))

                        # veracity_score = max(0, min(100, veracity_score))
                        veracity_score, analysis_content = parse_analysis_response(full_text)

                        current_analysis.veracity_score = float(veracity_score) / 100
                        # current_analysis.analysis_text = analysis_content

                        current_analysis.analysis_text = clean_unicode_text(analysis_content)
                        current_analysis.status = AnalysisStatus.completed.value
                        current_analysis.updated_at = datetime.now(UTC)

                        if not default:

                            await self._analysis_repo._session.rollback()

                            con_score = await self._generate_logprob_confidence_score(log_probs=log_probs)
                            logger.info(con_score)
                            current_analysis.confidence_score = float(con_score)
                            # log_data = await self._get_anth_confidence_score(statement=claim_text, veracity_score=veracity_score)
                            log_data = LogProbsData(tokens=analysis_text, probs=log_probs)
                            current_analysis.log_probs = log_data

                        stage = time.perf_counter()
                        updated_analysis = await self._analysis_repo.update_stream_safe(current_analysis)
                        timings["save"] = _elapsed_ms(stage)

                        evidence = [f"{source.title} {source.snippet}" for source in all_sources]
                        if looks_like_injection(claim_text, *evidence):
                            # One poisoned verdict in the shared cache would be served to other users.
                            logger.warning(f"Injection markers in analysis {current_analysis.id}: verdict not cached")
                        elif timings.get("planned_turn"):
                            # Its first search came from the user's clarification answers, which are not part of the
                            # claim text other users' checks are matched on, so this verdict stays out of the cache
                            logger.info(f"Analysis {current_analysis.id} used a planned search: verdict not cached")
                        elif cache_embedding is not None and cache_hit is None:
                            stage = time.perf_counter()
                            await self._cache_store(cache_embedding, claim_text, language, cache_key, updated_analysis)
                            timings["cache_store"] = _elapsed_ms(stage)
                        if subclaim_entries:
                            stage = time.perf_counter()
                            await self._subclaim_store(subclaim_entries, language, preferred_domains)
                            timings["subclaim_store"] = _elapsed_ms(stage)
                        timings["total"] = _elapsed_ms(started)
                        logger.info(f"Analysis timings: {timings}")

                        yield {
                            "type": "analysis_complete",
                            "content": {
                                "analysis_id": str(updated_analysis.id),
                                "veracity_score": updated_analysis.veracity_score,
                                "num_sources": len(all_sources),
                                "source_credibility": source_credibility,
                                **SemanticCacheService.hit_metadata(cache_hit),
                                **({"subclaims": subclaims} if subclaims else {}),
                                "timings_ms": timings,
                            },
                        }

                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parsing error: {str(e)}\nFull text: {full_text}")
                        import re

                        try:
                            veracity_match = re.search(r'"veracity_score"\s*:\s*([0-9]+(?:\.\d+)?)', full_text)
                            analysis_match = re.search(r'"analysis"\s*:\s*"((?:[^"\\]|\\.)*)"', full_text, re.DOTALL)
                            logger.info("Successfully found regex matches")
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
                            yield {"type": "error", "content": STREAM_ERROR}
                            raise

                    # except Exception as e:
                    #    logger.error(f"Error processing analysis: {str(e)}")
                    #    current_analysis.status = AnalysisStatus.failed.value
                    #    await self._analysis_repo.update(current_analysis)
                    #    yield {"type": "error", "content": f"Error creating analysis: {str(e)}"}
                    #    raise

                    except Exception as e:
                        logger.error(
                            "Error processing analysis response: %s\nFull text: %r",
                            str(e),
                            full_text[:2000],
                            exc_info=True,
                        )

                        current_analysis.status = AnalysisStatus.failed.value
                        current_analysis.analysis_text = clean_unicode_text(full_text)
                        await self._analysis_repo.update(current_analysis)

                        yield {
                            "type": "error",
                            "content": "Sorry, we couldn’t complete the analysis. Please try again.",
                        }
                        return

        except Exception as e:
            logger.error(f"Error in _generate_analysis: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "content": "Sorry, we couldn’t complete the analysis. Please try again.",
            }
            return

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
            yield {"type": "error", "content": STREAM_ERROR}

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

    async def _cache_lookup(
        self,
        claim_text: str,
        language: str,
        cache_key: Optional[str],
        cache_policy: Optional[CachePolicy],
        timings: Optional[Dict[str, int]] = None,
    ) -> tuple[Optional[List[float]], Optional[CacheHit]]:
        """Find a reusable cached analysis and return the claim embedding for storing a fresh result.

        Exact (normalized) matches skip the embedding call; otherwise pgvector proposes candidates and the
        NLI verifier decides. Cache failures never fail the analysis.
        """
        if not self._cache or not cache_policy or not cache_policy.write or not cache_policy.claim:
            return None, None
        timings = {} if timings is None else timings
        try:
            stage = time.perf_counter()
            hit = (
                await self._cache.exact_lookup(claim_text, language, cache_key, cache_policy.max_age_hours)
                if cache_policy.read
                else None
            )
            timings["cache_exact"] = _elapsed_ms(stage)
            embedding = None
            if hit is None or settings.SEMANTIC_CACHE_MODE == "shadow":
                stage = time.perf_counter()
                embedding = await self._cache.embed(claim_text)
                timings["cache_embed"] = _elapsed_ms(stage)
            if hit is None and cache_policy.read and cache_policy.claim_nli and settings.SEMCACHE_NLI_ENABLED:
                stage = time.perf_counter()
                candidates = await self._cache.candidates(embedding, language, cache_key, cache_policy.max_age_hours)
                timings["cache_candidates"] = _elapsed_ms(stage)
                timings["n_candidates"] = len(candidates)
                stage = time.perf_counter()
                hit = await self._cache.select_hit(claim_text, candidates)
                timings["cache_verify"] = _elapsed_ms(stage)
            if hit:
                logger.info(
                    f"Semantic cache {hit.tier} hit: reason={hit.reason} similarity={hit.similarity:.4f} "
                    f"mode={settings.SEMANTIC_CACHE_MODE} cached_at={hit.cached_at.isoformat()}"
                )
                if settings.SEMANTIC_CACHE_MODE == "shadow":
                    hit = None
            return embedding, hit
        except Exception as e:
            logger.error(f"Semantic cache lookup failed, running full analysis: {str(e)}", exc_info=True)
            await self._cache.rollback()
            return None, None

    async def _cache_store(
        self, embedding: List[float], claim_text: str, language: str, cache_key: str, analysis: Analysis
    ) -> None:
        try:
            await self._cache.store(
                embedding=embedding,
                claim_text=claim_text,
                language=language,
                params_hash=cache_key,
                analysis_id=analysis.id,
                veracity_score=analysis.veracity_score,
                analysis_text=analysis.analysis_text,
            )
        except Exception as e:
            logger.error(f"Semantic cache store failed: {str(e)}", exc_info=True)
            await self._cache.rollback()

    async def _claim_cache_hit(
        self, cache_hit: Optional[CacheHit], analysis_id: UUID, timings: Dict[str, int]
    ) -> tuple[Optional[CacheHit], List[SourceModel]]:
        """Copy a hit's sources to the new analysis. A hit whose analysis was deleted from the app DB is dropped."""
        if cache_hit is None:
            return None, []
        stage = time.perf_counter()
        cloned = await self._clone_cached_sources(cache_hit.source_analysis_id, analysis_id)
        timings["cache_clone"] = _elapsed_ms(stage)
        if cloned is None:
            await self._cache.invalidate(cache_hit.entry_id)
            return None, []
        await self._cache.record_hit(cache_hit.entry_id)
        return cache_hit, cloned

    def _evidence_prompt(self, sources: List[SourceModel], language: str) -> str:
        """Retrieved text fenced as data: a page can address the model or imitate our source format."""
        note = AnalysisPrompt.UNTRUSTED_SOURCES if language == "english" else AnalysisPrompt.UNTRUSTED_SOURCES_FR
        return f"{note}\n{wrap_untrusted(self._web_search.format_sources_for_prompt(sources, language))}"

    def _cached_evidence_messages(self, query: str, language: str, sources: List[SourceModel]) -> List[LLMMessage]:
        label = "Search result" if language == "english" else "Résultat(s) de la recherche sur le Web"
        sources_prompt = self._evidence_prompt(sources, language)
        return [
            LLMMessage(role="user", content=f"{query}\n\n{label}: {sources_prompt}"),
            LLMMessage(role="assistant", content="READY" if language == "english" else "PRÊT"),
        ]

    async def _clone_cached_sources(self, source_analysis_id: UUID, analysis_id: UUID) -> Optional[List[SourceModel]]:
        """Copy the cached analysis's searches and sources under the new analysis; None if it no longer exists."""
        cached = await self._analysis_repo.get_with_relations(source_analysis_id)
        if cached is None:
            return None
        all_sources = []
        for cached_search in cached.searches or []:
            if cached_search.summary == FOLLOWUP_SEARCH_SUMMARY:
                continue  # found in follow-up chat, not evidence for the cached verdict
            all_sources += await self._clone_search(
                cached_search.prompt, cached_search.summary, cached_search.sources or [], analysis_id
            )
        await self._search_repo._session.commit()
        return all_sources

    async def _clone_search(
        self, prompt: str, summary: Optional[str], cached_sources: List[Any], analysis_id: UUID
    ) -> List[SourceModel]:
        """Copy one cached search and its sources under `analysis_id`; the caller commits."""
        search = await self._search_repo.create(
            Search(
                id=uuid4(),
                analysis_id=analysis_id,
                prompt=prompt,
                summary=summary,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        sources = []
        for cached_source in cached_sources:
            source = await self._source_repo.create_with_domain(
                SourceModel(
                    id=uuid4(),
                    search_id=search.id,
                    url=cached_source.url,
                    title=cached_source.title,
                    snippet=cached_source.snippet,
                    domain_id=cached_source.domain_id,
                    content=cached_source.content,
                    credibility_score=cached_source.credibility_score,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            sources.append(source)
        return sources

    async def _subclaim_evidence(
        self,
        claim_text: str,
        query: str,
        language: str,
        analysis_id: UUID,
        preferred_domains: Optional[List[str]],
        cache_policy: Optional[CachePolicy],
        timings: Dict[str, int],
    ) -> tuple[List[str], List[LLMMessage], List[SourceModel], List[tuple]]:
        """Decompose the claim, then reuse each subclaim's cached search or run a new one.

        Returns the subclaims, the first planner message seeded with each subclaim's evidence, all sources, and
        (subclaim, embedding, search_id, sources) for the fresh searches that should be cached after the verdict.
        """
        await self._analysis_repo._session.rollback()
        stage = time.perf_counter()
        subclaims = await claim_decomposition.decompose(claim_text)
        timings["decompose"] = _elapsed_ms(stage)
        timings["n_subclaims"] = len(subclaims)

        hits: List[Optional[SubclaimHit]] = [None] * len(subclaims)
        embeddings = None
        if self._cache and cache_policy and cache_policy.write and settings.SUBCLAIM_CACHE_ENABLED:
            stage = time.perf_counter()
            try:
                embeddings = await self._cache.embed_many(subclaims)
                if cache_policy.read:
                    params_hash = self._subclaim_params_hash(language, preferred_domains)
                    hits = await self._cache.subclaim_lookup(
                        subclaims, embeddings, language, params_hash, cache_policy.max_age_hours
                    )
            except Exception as e:
                logger.error(f"Subclaim cache lookup failed, searching every subclaim: {str(e)}", exc_info=True)
                await self._cache.rollback()
                embeddings, hits = None, [None] * len(subclaims)
            timings["subclaim_lookup"] = _elapsed_ms(stage)
        timings["subclaim_cache_hits"] = sum(1 for hit in hits if hit)
        timings["subclaim_searches"] = 0

        # The provider calls for every miss run at once; saving their sources shares the DB session, so it doesn't
        misses = [i for i, hit in enumerate(hits) if not hit]
        stage = time.perf_counter()
        fetched = await asyncio.gather(
            *(self._web_search.fetch_results(subclaims[i], language, preferred_domains) for i in misses),
            return_exceptions=True,
        )
        results = {i: [] if isinstance(items, BaseException) else items for i, items in zip(misses, fetched)}
        if misses:
            timings["subclaim_search"] = _elapsed_ms(stage)

        label = "Sub-claim" if language == "english" else "Sous-affirmation"
        result_label = "Search result" if language == "english" else "Résultat(s) de la recherche sur le Web"
        blocks, all_sources, entries = [], [], []
        for i, (subclaim, hit) in enumerate(zip(subclaims, hits)):
            stage = time.perf_counter()
            if hit:
                sources = await self._clone_search(subclaim, SUBCLAIM_SEARCH_SUMMARY, hit.sources, analysis_id)
                await self._search_repo._session.commit()
                _add_elapsed(timings, "subclaim_clone", stage)
            else:
                search = await self._search_repo.create(
                    Search(
                        id=uuid4(),
                        analysis_id=analysis_id,
                        prompt=subclaim,
                        summary=SUBCLAIM_SEARCH_SUMMARY,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
                await self._search_repo._session.commit()
                sources = await self._web_search.create_sources(results[i], search.id, preferred_domains)
                timings["subclaim_searches"] += 1
                _add_elapsed(timings, "subclaim_save", stage)
                if embeddings is not None and sources:
                    entries.append((subclaim, embeddings[i], search.id, sources))
            await self._analysis_repo._session.rollback()
            all_sources += sources
            blocks.append(
                f"{label} {i + 1}: {flatten_untrusted(subclaim)}\n{result_label}: {self._evidence_prompt(sources, language)}"
            )

        note = (
            AnalysisPrompt.SUBCLAIM_EVIDENCE_NOTE if language == "english" else AnalysisPrompt.SUBCLAIM_EVIDENCE_NOTE_FR
        )
        messages = [LLMMessage(role="user", content=f"{query}\n\n{note}\n\n" + "\n\n".join(blocks))]
        return subclaims, messages, all_sources, entries

    def _subclaim_params_hash(self, language: str, preferred_domains: Optional[List[str]]) -> str:
        return SemanticCacheService.subclaim_params_hash(language, preferred_domains, type(self._web_search).__name__)

    @staticmethod
    def _subclaim_rules(subclaims: Optional[List[str]], language: str) -> str:
        """Algorithm 1 of CAAFC added to the verdict request; nothing for a claim that was not split."""
        if not subclaims or len(subclaims) < 2:
            return ""
        listed = "\n".join(f"{i}. {flatten_untrusted(s)}" for i, s in enumerate(subclaims, 1))
        rules = (
            AnalysisPrompt.SUBCLAIM_VERDICT_RULES if language == "english" else AnalysisPrompt.SUBCLAIM_VERDICT_RULES_FR
        )
        return "\n" + rules.format(subclaims=listed)

    async def _subclaim_store(
        self, entries: List[tuple], language: str, preferred_domains: Optional[List[str]]
    ) -> None:
        """Cache freshly searched subclaims, except where the subclaim or its evidence carries injection markers."""
        safe = []
        for subclaim, embedding, search_id, sources in entries:
            if looks_like_injection(subclaim, *[f"{s.title} {s.snippet}" for s in sources]):
                logger.warning(f"Injection markers in subclaim evidence: search {search_id} not cached")
            else:
                safe.append((subclaim, embedding, search_id))
        if not safe:
            return
        try:
            await self._cache.store_subclaims(safe, language, self._subclaim_params_hash(language, preferred_domains))
        except Exception as e:
            logger.error(f"Subclaim cache store failed: {str(e)}", exc_info=True)
            await self._cache.rollback()

    async def _replay_cached_analysis(
        self,
        current_analysis: Analysis,
        cache_hit: CacheHit,
        all_sources: List[SourceModel],
        timings: Dict[str, int],
        started: float,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Emit a cached analysis with the same events a live run produces."""
        stage = time.perf_counter()
        source_credibility = self._web_search.calculate_overall_credibility(all_sources)
        yield {
            "type": "status",
            "content": f"Found {len(all_sources)} relevant sources (overall credibility: {source_credibility:.2f})",
        }
        yield {"type": "status", "content": "Analyzing claim with gathered sources..."}

        raw = json.dumps(
            {"veracity_score": round(cache_hit.veracity_score * 100), "analysis": cache_hit.analysis_text},
            ensure_ascii=False,
        )
        for piece in split_for_replay(raw):
            yield {"type": "content", "content": piece}
            await asyncio.sleep(settings.SEMCACHE_REPLAY_DELAY_MS / 1000)

        current_analysis.veracity_score = cache_hit.veracity_score
        current_analysis.analysis_text = cache_hit.analysis_text
        current_analysis.status = AnalysisStatus.completed.value
        current_analysis.updated_at = datetime.now(UTC)
        updated_analysis = await self._analysis_repo.update_stream_safe(current_analysis)
        timings["replay"] = _elapsed_ms(stage)
        timings["total"] = _elapsed_ms(started)
        logger.info(f"Analysis timings: {timings}")

        yield {
            "type": "analysis_complete",
            "content": {
                "analysis_id": str(updated_analysis.id),
                "veracity_score": updated_analysis.veracity_score,
                "num_sources": len(all_sources),
                "source_credibility": source_credibility,
                **SemanticCacheService.hit_metadata(cache_hit),
                "timings_ms": timings,
            },
        }

    async def analyze_claim_stream(
        self,
        claim: Claim,
        user_id: UUID,
        default: bool = True,
        preferred_domains: list[str] | None = None,
        bypass_cache: bool = False,
        eval_mode: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream the analysis process for a claim and initialize conversation."""
        try:
            logger.info(f"Starting analysis for claim {claim.id}")

            # claim = await self._claim_repo.get(claim.id)
            if not claim:
                raise ValueError("Claim not found")

            logger.debug(f"Retrieved claim: {claim.claim_text}")
            self._analysis_state.current_claim = claim

            await self._claim_repo.update_status(claim.id, ClaimStatus.analyzing)

            yield {"type": "status", "content": "Starting analysis..."}

            # Generate analysis
            analysis_complete = False

            async for chunk in self._generate_analysis(
                claim.claim_text,
                claim.context,
                claim.language,
                default=default,
                preferred_domains=preferred_domains,
                cache_policy=SemanticCacheService.policy(bypass_cache=bypass_cache, eval_mode=eval_mode),
            ):
                if chunk["type"] == "analysis_complete":
                    analysis_complete = True
                    stage = time.perf_counter()
                    # Get the full analysis to create conversation
                    analysis = await self._analysis_repo.get(UUID(chunk["content"]["analysis_id"]))

                    # Initialize conversation structure
                    conversation_ids = await self.initialize_claim_conversation(
                        user_id=user_id,
                        claim_text=claim.claim_text,
                        analysis_text=analysis.analysis_text,
                        claim_id=claim.id,
                        analysis_id=analysis.id,
                    )

                    # Add conversation IDs to the response
                    chunk["content"]["conversation_id"] = str(conversation_ids["conversation_id"])
                    chunk["content"]["claim_conversation_id"] = str(conversation_ids["claim_conversation_id"])
                    # Runs after the verdict but before the client sees analysis_complete
                    chunk["content"].setdefault("timings_ms", {})["conversation_init"] = _elapsed_ms(stage)

                yield chunk

            if analysis_complete:
                await self._claim_repo.update_status(claim.id, ClaimStatus.analyzed)
                logger.info(f"Completed analysis for claim {claim.id}")
            else:
                await self._claim_repo.update_status(claim.id, ClaimStatus.failed)
                logger.error(f"Analysis incomplete for claim {claim.id}")

        except Exception as e:
            logger.error(f"Error in analyze_claim_stream: {str(e)}", exc_info=True)
            if self._analysis_state.current_claim:
                await self._claim_repo.update_status(claim.id, ClaimStatus.rejected)
            yield {"type": "error", "content": STREAM_ERROR}
            raise

    async def analyze_claim_direct(self, claim_id: UUID, user_id: UUID, eval_mode: bool = False) -> Dict[str, Any]:
        claim = await self._claim_repo.get(claim_id)
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")

        self._analysis_state.current_claim = claim
        await self._claim_repo.update_status(claim_id, ClaimStatus.analyzing)

        analysis_complete = False
        final_chunk = None

        async for chunk in self._generate_analysis(
            claim.claim_text,
            claim.context,
            claim.language,
            cache_policy=SemanticCacheService.policy(eval_mode=eval_mode, batch=True),
        ):
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
        """Stream interactive discussion about a claim.

        Each follow-up is routed first: answer from the gathered sources, run one extra search, or propose
        re-checking a revised claim (emitted as `recheck_proposed`; the client submits it via POST /claims/).
        """
        started = time.perf_counter()
        # Per-stage durations, sent with message_complete
        timings: Dict[str, int] = {}
        try:
            # First verify the conversation belongs to the user
            conversation = await self._conversation_repo.get(conversation_id)
            if not conversation or conversation.user_id != user_id:
                raise NotAuthorizedException("Not authorized to access this conversation")

            # Verify the claim conversation, and that it is about this claim, since its sources go into the prompt
            claim_conv = await self._claim_conversation_repo.get(claim_conversation_id)
            if not claim_conv or claim_conv.conversation_id != conversation_id or claim_conv.claim_id != claim_id:
                raise NotAuthorizedException("Not authorized to access this claim conversation")

            # Get claim and latest analysis, with its sources, for context
            claim = await self._claim_repo.get(claim_id)
            if not claim:
                raise NotFoundException("Claim not found")

            analyses = await self._analysis_repo.get_by_claim(
                claim_id=claim_id, include_searches=True, include_sources=True
            )
            analysis = analyses[-1] if analyses else None

            if not analysis:
                raise NotFoundException("Analysis not found")

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

            # Get conversation context (last few messages, excluding the one just stored)
            context_messages = await self._message_repo.get_claim_conversation_messages(
                claim_conversation_id=claim_conversation_id,
                limit=11,
            )
            context_messages = [msg for msg in reversed(context_messages) if msg.id != user_message.id][-10:]

            sources = [source for search in analysis.searches or [] for source in search.sources or []]
            timings["context_load"] = _elapsed_ms(started)
            # A follow-up can turn into a web search or a new check, so it is screened like a claim
            harmful = False
            if settings.HARM_CHECK_ENABLED:
                stage = time.perf_counter()
                # With the conversation, so "now write the steps as a list" is judged by what it refers to
                earlier = [m.content[:300] for m in context_messages if m.sender_type != MessageSenderType.bot][-3:]
                harmful = await self._is_harmful_request(
                    f"Claim being discussed: {claim.claim_text}\n"
                    + "".join(f"Earlier user message: {text}\n" for text in earlier)
                    + f"Latest user message, to judge: {message_content}"
                )
                timings["harm_check"] = _elapsed_ms(stage)
            stage = time.perf_counter()
            if harmful:
                logger.warning(f"Follow-up refused as a request for harmful help: claim {claim_id}")
                action, argument = FOLLOWUP_ANSWER, ""
            elif settings.MULTITURN_ENABLED:
                action, argument = await self._route_followup(
                    claim, analysis, sources, context_messages, message_content
                )
            else:
                action, argument = FOLLOWUP_ANSWER, ""
            timings["router"] = _elapsed_ms(stage)
            yield {"type": "router_decision", "content": action}

            if action == FOLLOWUP_SEARCH:
                stage = time.perf_counter()
                sources = sources + await self._followup_search(analysis.id, argument, claim.language)
                timings["web_search"] = _elapsed_ms(stage)
            elif action == FOLLOWUP_RECHECK:
                yield {"type": "recheck_proposed", "content": {"claim_text": argument}}

            # Create LLM messages from context
            llm_messages = [
                LLMMessage(
                    role="assistant" if msg.sender_type == MessageSenderType.bot else "user", content=msg.content
                )
                for msg in context_messages
            ]

            canary = secrets.token_hex(4)

            # Add current message. For a re-check the instruction rides on the user turn: the model follows that
            # over a system-prompt note when earlier turns pull the reply elsewhere.
            if action == FOLLOWUP_RECHECK:
                message_content = (
                    f"{message_content}\n\n(Assistant instruction {canary}: this message changes the claim to '{argument}'. "
                    "Do not answer anything else. In at most three sentences, say that this revised claim needs a new "
                    "fact-check, which I can start with the re-check button, and what, if anything, the sources "
                    "gathered so far already say about it.)"
                )
            reminder = AnalysisPrompt.FOLLOWUP_REMINDER.format(canary=canary)
            llm_messages.append(LLMMessage(role="user", content=f"{message_content}\n\n{reminder}"))

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

            # Data first and rules last: the model weighs what it read most recently.
            data = wrap_untrusted(
                f"Claim: {flatten_untrusted(claim.claim_text)}\n"
                + (f"Context provided with the claim: {flatten_untrusted(claim.context)}\n" if claim.context else "")
                + "Sources gathered so far:\n"
                + self._web_search.format_sources_for_prompt(sources, claim.language)
            )
            system_context = (
                f"Reference code: {canary}. You are a fact-checking assistant. The user is asking about this claim.\n"
                f"Your previous analysis determined this claim is {analysis.veracity_score * 100:.1f}% likely to be true"
                # Providers without logprobs store 0 confidence; don't let the model quote it to the user.
                + (f" with {analysis.confidence_score * 100:.1f}% confidence" if analysis.confidence_score else "")
                + ".\n"
                + f"{data}\n\n"
                + AnalysisPrompt.FOLLOWUP_RULES.format(canary=canary)
            )
            llm_messages.insert(0, LLMMessage(role="system", content=system_context))

            response_content = []
            stage = time.perf_counter()
            replies = _single_reply(FOLLOWUP_REFUSAL) if harmful else self._guarded_reply(llm_messages, canary)
            async for text in replies:
                timings.setdefault("answer_ttft", _elapsed_ms(stage))
                response_content.append(text)
                yield {"type": "content", "content": text, "message_id": str(bot_message.id)}
            timings["answer"] = _elapsed_ms(stage)

            # Update bot message with complete response when done
            bot_message.content = "".join(response_content)
            await self._message_repo.update(bot_message)
            timings["total"] = _elapsed_ms(started)
            logger.info(f"Follow-up timings: route={action} {timings}")

            yield {"type": "message_complete", "message_id": str(bot_message.id), "timings_ms": timings}

        except Exception as e:
            logger.error(f"Error in stream_claim_discussion: {str(e)}", exc_info=True)
            yield {"type": "error", "content": STREAM_ERROR}
            raise

    async def _guarded_reply(self, messages: List[LLMMessage], canary: str) -> AsyncGenerator[str, None]:
        """Stream a reply, replacing it if it leaks the prompt or the provider's safety filter cuts it off.

        The canary opens the system prompt, and the first characters are held back, so a verbatim leak or an
        immediate block never reaches the user as a fragment.
        """
        reply, held = "", ""
        async for chunk in self._llm.generate_stream(messages, temperature=0.7):
            reply += chunk.text
            held += chunk.text
            blocked = chunk.metadata.get("finish_reason") in CONTENT_FILTER_REASONS
            if canary in reply or blocked:
                logger.warning(f"Follow-up reply replaced: blocked={blocked} leaked={canary in reply}")
                yield FOLLOWUP_REFUSAL if len(reply) == len(held) else f"\n\n{FOLLOWUP_REFUSAL}"
                return
            if len(reply) >= REPLY_HOLD_CHARS and held:
                yield held
                held = ""
        # A safety block mid-stream can end as a normal "stop" with the reply cut to a word or less.
        if len(reply.strip()) < MIN_REPLY_CHARS:
            logger.warning("Follow-up reply replaced: cut off by the provider")
            yield FOLLOWUP_REFUSAL
        elif held:
            yield held

    async def _route_followup(
        self, claim: Claim, analysis: Analysis, sources: List[Any], history: List[Message], message: str
    ) -> tuple[str, str]:
        """Decide whether a follow-up is answered from existing evidence, needs a search, or needs a re-check."""
        titles = "\n".join(f"- {source.title}" for source in sources[:30]) or "(none)"
        history_text = (
            "\n".join(
                f"{'assistant' if msg.sender_type == MessageSenderType.bot else 'user'}: {msg.content[:500]}"
                for msg in history[-6:]
            )
            or "(none)"
        )
        prompt = AnalysisPrompt.FOLLOWUP_ROUTER.format(
            claim=claim.claim_text,
            veracity=(analysis.veracity_score or 0) * 100,
            source_titles=titles,
            history=wrap_untrusted(history_text),
            message=wrap_untrusted(message),
        )
        try:
            response = await self._llm.generate_response([LLMMessage(role="user", content=prompt)], temperature=0.0)
        except Exception as e:
            logger.error(f"Follow-up routing failed, answering from existing evidence: {str(e)}", exc_info=True)
            return FOLLOWUP_ANSWER, ""
        return parse_followup_route(getattr(response, "text", "") or "")

    async def _followup_search(self, analysis_id: UUID, query: str, language: str) -> List[SourceModel]:
        """Run one web search for a follow-up question; its sources are kept under the analysis for later turns."""
        try:
            search = await self._search_repo.create(
                Search(
                    id=uuid4(),
                    analysis_id=analysis_id,
                    prompt=query,
                    summary=FOLLOWUP_SEARCH_SUMMARY,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            await self._search_repo._session.commit()
            return await self._web_search.search_and_create_sources(
                claim_text=query, search_id=search.id, language=language
            )
        except Exception as e:
            logger.error(f"Follow-up search failed: {str(e)}", exc_info=True)
            return []

    def clean_text(text):
        cleaned_text = re.sub(r"[^a-zA-Z,.?!' ]", "", text)
        return cleaned_text

    async def _is_harmful_request(self, text: str) -> bool:
        """Whether a claim or follow-up is really a request for help causing harm. Claims that attack a group are
        still checked (debunking them is the job). Fails open: on an error the check goes ahead, logged."""
        return (await screen_text(self._llm, text)).harmful

    def _query_initial(self, statement: str, language: str):

        if language == "english":
            return AnalysisPrompt.ORCHESTRATOR_PROMPT.format(statement=statement, date=datetime.now().isoformat())
        elif language == "french":
            return AnalysisPrompt.ORCHESTRATOR_PROMPT_FR.format(statement=statement, date=datetime.now().isoformat())
        else:
            raise ValidationError("Claim Language is invalid")

    async def _generate_logprob_confidence_score(self, log_probs: list[float]):
        if not log_probs:
            return 0.0

        try:
            # 1. Calculate the average of the log-probabilities
            #    (This represents the geometric mean in log-space)
            avg_logprob = sum(log_probs) / len(log_probs)

            # 2. Convert back to linear probability (0.0 to 1.0)
            return math.exp(avg_logprob)

        except Exception:
            # Safety fallback for edge cases like overflow (unlikely with logprobs)
            return 0.0

    async def _generate_confidence_score(self, statement: str, analysis: str, sources: str, veracity: str):
        messages = [
            LLMMessage(
                role="user",
                content=AnalysisPrompt.GET_CONFIDENCE.format(
                    date=datetime.now().isoformat(),
                    statement=statement,
                    analysis=analysis,
                    sources=sources,
                    veracity=veracity,
                ),
            )
        ]
        response = await self._llm.generate_response(messages)
        text = response.text
        logger.warning(text)

        match = re.findall(r"\d+", text)

        if match:
            return match[-1]

        return ""

    async def _get_anth_confidence_score(self, statement: str, veracity_score: float):
        # label = 'true'
        # if veracity_score < 50:
        #     label ='false'
        # elif veracity_score == 50:
        #     label = 'unknown'

        messages = [
            LLMMessage(
                role="user",
                content=AnalysisPrompt.GET_ANTH_CONFIDENCE_MOD_2.format(
                    date=datetime.now().isoformat(),
                    statement=statement,
                    score=veracity_score,
                ),
            )
        ]
        response = await self._llm.generate_response(messages)
        raw_logprobs = response.metadata.get("raw_logprobs")

        # Initialize defaults
        log_probs_obj = LogProbsData(anth_conf_score=0, tokens=[], probs=[], alternatives=[])

        if raw_logprobs:
            # 2. Get the log_prob for "Yes" from the first token's alternatives
            # First entry in top_logprobs list, get the value for key 'Yes'
            first_token_alts = raw_logprobs.top_logprobs[0]

            p_yes = sum(math.exp(val) for key, val in first_token_alts.items() if key.strip().lower() == "yes")

            p_no = sum(math.exp(val) for key, val in first_token_alts.items() if key.strip().lower() == "no")

            # Convert log probability to linear probability: p = exp(log_p)
            pvlm_score = 0
            if p_yes + p_no == 0:
                pvlm_score = 0.5  # Neutral/Uncertain
            else:
                pvlm_score = p_yes / (p_yes + p_no)

            # 3. Construct the LogProbsData object
            log_probs_obj = LogProbsData(
                anth_conf_score=pvlm_score,
                tokens=raw_logprobs.tokens,
                probs=raw_logprobs.token_logprobs,
                alternatives=raw_logprobs.top_logprobs,
            )
        logger.info(f"Confidence: {pvlm_score}, Data: {log_probs_obj}")
        return log_probs_obj

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

    async def vary_analysis_assertiveness(self, analysis_id: UUID) -> Analysis:
        """Get analysis by ID, and return different assertivity"""
        analysis = await self._analysis_repo.get(analysis_id)

        if not analysis:
            raise NotFoundException("Analysis not found")

        claim = await self._claim_repo.get(analysis.claim_id)
        if not claim:
            raise NotFoundException("Claim not found")

        assertiveness = claim.batch_post_id

        analysis_copy = deepcopy(analysis)

        if assertiveness == "med":
            pass
        elif assertiveness == "low" or assertiveness == "high":
            analysis_copy.analysis_text = await self._llm_message_assertivity(
                analysis_copy.analysis_text, assertiveness
            )
            claim.context = analysis_copy.analysis_text
            await self._claim_repo.update(claim)
            return analysis_copy
        else:
            raise NotFoundException("Assertivity was NOT properly set before the Get request was made.")

        return analysis_copy

    async def _llm_message_assertivity(self, text, assertiveness):

        messages = [
            LLMMessage(role="user", content=f"The analysis text is {text}"),
            LLMMessage(
                role="user",
                content=(
                    AnalysisPrompt.HIGH_ASSERT.format(original_length=str(len(text.split())))
                    if assertiveness == "high"
                    else AnalysisPrompt.LOW_ASSERT.format(original_length=str(len(text.split())))
                ),
            ),
        ]

        response = await self._llm.generate_response(messages)

        main_agent_message = response.text

        assert main_agent_message is not None, (
            "Invalid Main Agent API response:",
            response,
        )

        return main_agent_message
