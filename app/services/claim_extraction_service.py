import json
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message as LLMMessage
from app.core.llm.prompts import AnalysisPrompt
from app.core.text_safety import clean_unicode_text, extract_json_candidate, wrap_untrusted
from app.services.harm_screen import screen_text

logger = logging.getLogger(__name__)

REASON_OK = "ok"
REASON_NO_CLAIMS = "no_claims"
REASON_LLM_ERROR = "llm_error"
REASON_TOO_LONG = "too_long"

# Keys the model may use to hold the statement list, in order of preference.
_STATEMENT_KEYS = ("statements", "claims", "facts", "results")
# Keys a statement object may use to hold its text.
_STATEMENT_TEXT_KEYS = ("text", "statement", "claim", "description")
# Tokens a naive quoted-string salvage must not mistake for a statement.
_JSON_KEYWORDS = frozenset(_STATEMENT_KEYS + _STATEMENT_TEXT_KEYS + ("true", "false", "null"))

MAX_STATEMENTS = 10
MAX_STATEMENT_CHARS = 1000
MIN_STATEMENT_CHARS = 8

CLARIFY_ASK = "ask"
CLARIFY_READY = "ready"
CLARIFY_NOT_A_CLAIM = "B"
# Clarifying questions asked before the claim is fact-checked anyway.
MAX_CLARIFY_ROUNDS = 2
MAX_CLARIFY_OPTIONS = 4
CLARIFY_HARMFUL = "C"
SKIPPED_ANSWER = (
    "(skipped: choose the most likely reading, or failing that the most common claim on the subject, "
    "and state it as an assumption)"
)
SKIPPED_ANSWER_FR = (
    "(ignorée : choisissez l'interprétation la plus probable, ou à défaut l'affirmation la plus courante "
    "sur le sujet, et indiquez-la comme hypothèse)"
)

# Turn 1 of the search loop, planned by the combined clarify call (USE_COMBINED_MULTI_PROMPT) and used once by
# the fact-check of the same claim. In memory: a miss (another pod, restart, edited claim) just runs turn 1 as before.
# Keyed by user: the query is written by the model from untrusted input and answers, so one user must never be able
# to plant the first search of another user's check of the same claim. Never planned for harmful (class C) input.
PLANNED_TURN_TTL_SECONDS = 900
MAX_PLANNED_TURNS = 1000
MAX_QUERY_CHARS = 500
_planned_turns: "OrderedDict[Tuple[str, str, str], Tuple[float, str]]" = OrderedDict()


def _planned_turn_key(claim: str, language: str, user_id) -> Tuple[str, str, str]:
    return str(user_id), language, " ".join(clean_unicode_text(claim).split())


def remember_planned_turn(claim: str, language: str, turn: str, user_id=None) -> None:
    key = _planned_turn_key(claim, language, user_id)
    _planned_turns[key] = (time.monotonic(), turn)
    _planned_turns.move_to_end(key)
    while len(_planned_turns) > MAX_PLANNED_TURNS:
        _planned_turns.popitem(last=False)


def take_planned_turn(claim: str, language: str, user_id=None) -> Optional[str]:
    """This user's planned turn-1 reply for this claim, if a recent clarify call made one. Each plan is used once."""
    entry = _planned_turns.pop(_planned_turn_key(claim, language, user_id), None)
    if entry and time.monotonic() - entry[0] < PLANNED_TURN_TTL_SECONDS:
        return entry[1]
    return None


@dataclass
class ExtractionResult:
    """Outcome of a claim extraction attempt."""

    statements: List[str] = field(default_factory=list)
    reason: str = REASON_OK


@dataclass
class ClarificationResult:
    """Either a clarifying question for the user, or the claim ready to fact-check."""

    status: str
    claim: str
    question: Optional[str] = None
    options: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)


def _clean_strings(values, limit: int) -> List[str]:
    if not isinstance(values, list):
        return []
    cleaned = [clean_unicode_text(v).strip() for v in values if isinstance(v, str)]
    return [v for v in cleaned if v][:limit]


def parse_clarification_response(raw_text: str, original_claim: str, allow_ask: bool) -> ClarificationResult:
    """Parse the clarification JSON. Anything unusable fails open to fact-checking the original claim."""
    try:
        data = json.loads(extract_json_candidate(raw_text))
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning(
            "Malformed clarification JSON from LLM. Proceeding without clarification. Raw=%r", raw_text[:2000]
        )
        return ClarificationResult(CLARIFY_READY, original_claim)

    if not isinstance(data, dict):
        return ClarificationResult(CLARIFY_READY, original_claim)

    question = clean_unicode_text(data.get("question") or "").strip()
    options = _clean_strings(data.get("options"), MAX_CLARIFY_OPTIONS)
    if allow_ask and data.get("status") == CLARIFY_ASK and question:
        return ClarificationResult(
            CLARIFY_ASK,
            original_claim,
            question=question,
            options=options,
        )

    claim = clean_unicode_text(data.get("claim") or "").strip()[:MAX_STATEMENT_CHARS]
    if not claim and data.get("input") == CLARIFY_NOT_A_CLAIM and options:
        # Asked again with no questions left: a non-claim's options are full claims, so check one over the raw topic.
        claim = options[0][:MAX_STATEMENT_CHARS]
    claim = claim or original_claim
    return ClarificationResult(CLARIFY_READY, claim, assumptions=_clean_strings(data.get("assumptions"), 5))


def _json_object(raw_text: str) -> dict:
    try:
        data = json.loads(extract_json_candidate(raw_text))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _refuse_harmful(result: ClarificationResult, data: dict, language: str) -> ClarificationResult:
    """A harmful input (class C) never becomes a check from the clarifier, at any round, and never gets suggestions.

    Past the question limit the parser would fall back to checking the text as written, which sent requests such
    as "how to make a pipe bomb" to web search. The user starts a new check with a factual claim instead.
    """
    if data.get("input") != CLARIFY_HARMFUL:
        return result
    refusal = (
        AnalysisPrompt.CLARIFY_HARMFUL_REFUSAL_FR if language == "french" else AnalysisPrompt.CLARIFY_HARMFUL_REFUSAL
    )
    return ClarificationResult(CLARIFY_ASK, result.claim, question=refusal, options=[])


MAX_UNNAMED = 3
MAX_UNNAMED_CHARS = 60
_PRONOUNS = frozenset("he she they him her them il elle ils elles".split())
_DETERMINERS = frozenset(
    "the this that these those their his her its le la les ce cet cette ces son sa ses leur leurs".split()
)


def _is_unnamed(phrase: str) -> bool:
    """A pronoun ("he") or a determiner plus common nouns ("the vaccine", "l'étude"), not a proper name."""
    words = re.split(r"[\s']+", phrase.strip())
    first = words[0].lower()
    if first in _PRONOUNS and len(words) == 1:
        return True
    if first not in _DETERMINERS and first != "l" or len(words) < 2:
        return False
    # "the Pfizer vaccine", "the Dayton Agreement": a capitalised word after the determiner is a name
    return not any(word[:1].isupper() for word in words[1:])


def _unnamed_subjects(data: dict, claim: str) -> List[str]:
    """Unnamed people or things the combined call quoted from a claim (class A).

    Kept only if the claim contains the phrase and it is lexically unnamed, so a model that lists a title or a name
    ("Arsenic and Old Lace") can't make the service ask about it.
    """
    if data.get("input") != "A":
        return []
    found = []
    for phrase in _clean_strings(data.get("unnamed"), MAX_UNNAMED):
        in_claim = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", claim, flags=re.IGNORECASE)
        if len(phrase) <= MAX_UNNAMED_CHARS and in_claim and _is_unnamed(in_claim.group(0)):
            found.append(in_claim.group(0))
    return found


def _to_items(data) -> List:
    """Pull the raw statement items out of whatever JSON shape the model returned."""
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        for key in _STATEMENT_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _item_to_text(item) -> Optional[str]:
    """Coerce one raw statement item to text, tolerating both strings and objects."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in _STATEMENT_TEXT_KEYS:
            value = item.get(key)
            if isinstance(value, str):
                return value
    return None


def _salvage_quoted_strings(candidate: str) -> List[str]:
    """Last-resort recovery of statement literals from malformed JSON.

    Mirrors the regex fallback in parse_analysis_response: when the model emits
    JSON that is truncated or missing a closing brace, the string literals are
    usually still intact and worth recovering rather than discarding the whole
    response.
    """
    matches = re.findall(r'"((?:[^"\\]|\\.){8,}?)"', candidate, flags=re.DOTALL)
    return [match for match in matches if match.strip().lower() not in _JSON_KEYWORDS]


def _normalise(items: List) -> List[str]:
    """Clean, deduplicate and cap the extracted statements, preserving order."""
    seen = set()
    statements: List[str] = []

    for item in items:
        text = clean_unicode_text(_item_to_text(item)).strip()
        text = text.strip('"').strip("'").strip()

        if len(text) < MIN_STATEMENT_CHARS:
            continue
        if len(text) > MAX_STATEMENT_CHARS:
            text = text[:MAX_STATEMENT_CHARS].rstrip()

        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        statements.append(text)

        if len(statements) >= MAX_STATEMENTS:
            break

    return statements


def parse_extraction_response(raw_text: str) -> List[str]:
    """Extract the statement list from a raw model completion."""
    candidate = extract_json_candidate(raw_text)

    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(
            "Malformed extraction JSON from LLM. Falling back to regex salvage. Error=%s Raw=%r",
            e,
            raw_text[:2000],
        )
        return _normalise(_salvage_quoted_strings(candidate))

    return _normalise(_to_items(data))


class ClaimExtractionService:
    """Extracts self-contained, verifiable statements from free text.

    Nothing is persisted: the caller decides which statement to fact-check, and
    only then is a Claim created through the normal claim pipeline.
    """

    def __init__(self, llm_provider: LLMProvider, max_input_chars: int = 8000):
        self._llm = llm_provider
        self._max_input_chars = max_input_chars

    async def extract_statements(self, text: str, language: str) -> ExtractionResult:
        cleaned, failure = self._prepare(text)
        if failure is not None:
            return ExtractionResult([], failure)

        messages = [LLMMessage(role="user", content=self._build_prompt(cleaned, language))]

        try:
            response = await self._llm.generate_response(messages, temperature=0.0)
        except Exception:
            logger.exception("Claim extraction LLM call failed")
            return ExtractionResult([], REASON_LLM_ERROR)

        statements = parse_extraction_response(getattr(response, "text", "") or "")

        if not statements:
            logger.info("Claim extraction produced no usable statements")
            return ExtractionResult([], REASON_NO_CLAIMS)

        return ExtractionResult(statements, REASON_OK)

    async def clarify(
        self, text: str, language: str, turns: List[Tuple[str, Optional[str]]], user_id=None
    ) -> ClarificationResult:
        """Ask one clarifying question if a missing detail would change the verdict, else return the claim to check.

        Stateless: the caller sends back every earlier (question, answer) pair; an answer of None means the user
        skipped it, so the model proceeds with a stated assumption. Errors fail open to the original claim, which
        the fact-check screens for harmful requests before searching.
        """
        claim = clean_unicode_text(text).strip()
        if not settings.MULTITURN_ENABLED:
            return ClarificationResult(CLARIFY_READY, claim)
        # A skipped question means "just check it": stop asking rather than rephrase the same question.
        allow_ask = len(turns) < MAX_CLARIFY_ROUNDS and all(answer for _, answer in turns)
        if settings.USE_COMBINED_MULTI_PROMPT:
            return await self._clarify_and_plan(claim, language, turns, allow_ask, user_id)
        messages = [LLMMessage(role="user", content=self._build_clarify_prompt(claim, language, turns, allow_ask))]

        started = time.perf_counter()
        try:
            response = await self._llm.generate_response(messages, temperature=0.0)
        except Exception:
            logger.exception("Claim clarification LLM call failed")
            return ClarificationResult(CLARIFY_READY, claim)

        raw = getattr(response, "text", "") or ""
        data = _json_object(raw)
        result = _refuse_harmful(parse_clarification_response(raw, claim, allow_ask), data, language)
        result = await self._screen_suggestions(result, data, claim, language)
        logger.info(
            f"Clarify timings: llm_ms={round((time.perf_counter() - started) * 1000)} "
            f"round={len(turns) + 1} status={result.status}"
        )
        return result

    async def _clarify_and_plan(
        self, claim: str, language: str, turns: List[Tuple[str, Optional[str]]], allow_ask: bool, user_id=None
    ) -> ClarificationResult:
        """One call returns either a clarifying question, or the claim plus the first search of its fact-check.

        The search is kept for take_planned_turn, so the fact-check skips its own turn-1 LLM call. Errors fail open
        the same way as the separate clarify call.
        """
        started = time.perf_counter()
        try:
            response = await self._llm.generate_response(
                self._build_plan_messages(claim, language, turns, allow_ask), temperature=0.0, json_mode=True
            )
        except Exception:
            logger.exception("Claim clarify-and-plan LLM call failed")
            return ClarificationResult(CLARIFY_READY, claim)

        raw = getattr(response, "text", "") or ""
        data = _json_object(raw)
        result = _refuse_harmful(parse_clarification_response(raw, claim, allow_ask), data, language)
        result = await self._screen_suggestions(result, data, claim, language)
        unnamed = _unnamed_subjects(data, claim) if allow_ask and not turns else []
        if unnamed:
            # An unnamed person or thing ("he", "the vaccine") leaves the claim uncheckable, and the model often
            # searches anyway or guesses who is meant, so code asks and never offers guesses. First round only,
            # so an answered question is never repeated.
            subjects = ", ".join(f'"{subject}"' for subject in unnamed)
            template = AnalysisPrompt.CLARIFY_UNNAMED_FR if language == "french" else AnalysisPrompt.CLARIFY_UNNAMED
            question = result.question if result.status == CLARIFY_ASK else template.format(subjects=subjects)
            result = ClarificationResult(CLARIFY_ASK, claim, question=question, options=[])
        query = " ".join(clean_unicode_text(data.get("query") or "").split())[:MAX_QUERY_CHARS]
        if result.status == CLARIFY_READY and query and data.get("input") in ("A", CLARIFY_NOT_A_CLAIM):
            reason = " ".join(clean_unicode_text(data.get("reason") or "").split())[:MAX_STATEMENT_CHARS]
            reason = reason or "Search for evidence about the claim."
            # Exactly the reply format the search loop's parser expects from turn 1
            separator = " :" if language == "french" else ":"
            turn = f"REASON{separator} {reason}\nSEARCH{separator} {query}"
            remember_planned_turn(result.claim, language, turn, user_id)
        logger.info(
            f"Clarify timings: llm_ms={round((time.perf_counter() - started) * 1000)} "
            f"round={len(turns) + 1} status={result.status} combined=1 planned={int(bool(query))}"
        )
        return result

    async def _screen_suggestions(
        self, result: ClarificationResult, data: dict, claim: str, language: str
    ) -> ClarificationResult:
        """Before suggesting claims for a non-claim input, check it is not a harmful request or an attack on a group.

        The model often classes "why immigrants ruin everything" as a topic and suggests "Immigrants increase crime
        rates", which repeats the attack back to the user. Only runs when suggestions are about to be shown.
        """
        if not (settings.HARM_CHECK_ENABLED and result.status == CLARIFY_ASK and result.options):
            return result
        if data.get("input") == "A":  # place and period options for a claim, not suggested claims
            return result
        screen = await screen_text(self._llm, claim)
        if screen.harmful or screen.attacks_group:
            logger.warning(
                f"Clarifier suggestions withheld: harmful={screen.harmful} attacks_group={screen.attacks_group}"
            )
            return _refuse_harmful(result, {"input": CLARIFY_HARMFUL}, language)
        return result

    def _build_plan_messages(
        self, claim: str, language: str, turns: List[Tuple[str, Optional[str]]], allow_ask: bool
    ) -> List[LLMMessage]:
        french = language == "french"
        skipped = AnalysisPrompt.CLARIFY_AND_PLAN_SKIPPED_FR if french else AnalysisPrompt.CLARIFY_AND_PLAN_SKIPPED
        lines = [f"Q: {question}\nA: {answer if answer else skipped}" for question, answer in turns]
        rules = "" if allow_ask else "\n" + AnalysisPrompt.CLARIFY_AND_PLAN_NO_MORE_QUESTIONS
        if french:
            rules += "\n" + AnalysisPrompt.CLARIFY_AND_PLAN_FRENCH
        user = AnalysisPrompt.CLARIFY_AND_PLAN_INPUT.format(
            date=datetime.now().isoformat(),
            claim=wrap_untrusted(claim),
            turns=wrap_untrusted("\n".join(lines) or "(none)"),
            rules=rules,
        )
        return [
            LLMMessage(role="system", content=AnalysisPrompt.CLARIFY_AND_PLAN),
            LLMMessage(role="user", content=user),
        ]

    def _prepare(self, text: str) -> Tuple[str, Optional[str]]:
        """Clean the input, or return the reason it cannot be processed."""
        cleaned = clean_unicode_text(text).strip()

        if not cleaned:
            return "", REASON_NO_CLAIMS

        if len(cleaned) > self._max_input_chars:
            # Refuse rather than truncate: extracting from only the head of a long
            # paste would leave the user confirming an incomplete list.
            logger.info(
                "Claim extraction refused: %d chars exceeds the %d char limit", len(cleaned), self._max_input_chars
            )
            return "", REASON_TOO_LONG

        return cleaned, None

    def _build_prompt(self, text: str, language: str) -> str:
        template = AnalysisPrompt.EXTRACT_CLAIMS_FR if language == "french" else AnalysisPrompt.EXTRACT_CLAIMS
        return template.format(text=wrap_untrusted(text))

    def _build_clarify_prompt(
        self, claim: str, language: str, turns: List[Tuple[str, Optional[str]]], allow_ask: bool
    ) -> str:
        french = language == "french"
        if french:
            skipped = SKIPPED_ANSWER_FR
            ask_rule = "" if allow_ask else 'Vous devez maintenant renvoyer le statut "ready".'
        else:
            skipped = SKIPPED_ANSWER
            ask_rule = "" if allow_ask else 'You must now return status "ready".'

        lines = [f"Q: {question}\nA: {answer if answer else skipped}" for question, answer in turns]
        template = AnalysisPrompt.CLARIFY_CLAIM_FR if french else AnalysisPrompt.CLARIFY_CLAIM
        return template.format(
            claim=wrap_untrusted(claim), turns=wrap_untrusted("\n".join(lines) or "(none)"), ask_rule=ask_rule
        )
