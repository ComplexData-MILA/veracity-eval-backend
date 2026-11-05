import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message as LLMMessage
from app.core.llm.prompts import AnalysisPrompt
from app.core.text_safety import clean_unicode_text, extract_json_candidate, wrap_untrusted

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

    async def clarify(self, text: str, language: str, turns: List[Tuple[str, Optional[str]]]) -> ClarificationResult:
        """Ask one clarifying question if a missing detail would change the verdict, else return the claim to check.

        Stateless: the caller sends back every earlier (question, answer) pair; an answer of None means the user
        skipped it, so the model proceeds with a stated assumption. Errors fail open to the original claim.
        """
        claim = clean_unicode_text(text).strip()
        if not settings.MULTITURN_ENABLED:
            return ClarificationResult(CLARIFY_READY, claim)
        # A skipped question means "just check it": stop asking rather than rephrase the same question.
        allow_ask = len(turns) < MAX_CLARIFY_ROUNDS and all(answer for _, answer in turns)
        messages = [LLMMessage(role="user", content=self._build_clarify_prompt(claim, language, turns, allow_ask))]

        try:
            response = await self._llm.generate_response(messages, temperature=0.0)
        except Exception:
            logger.exception("Claim clarification LLM call failed")
            return ClarificationResult(CLARIFY_READY, claim)

        return parse_clarification_response(getattr(response, "text", "") or "", claim, allow_ask)

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
            skipped = (
                "(ignorée : choisissez l'interprétation la plus probable, ou à défaut l'affirmation la plus courante "
                "sur le sujet, et indiquez-la comme hypothèse)"
            )
            ask_rule = "" if allow_ask else 'Vous devez maintenant renvoyer le statut "ready".'
        else:
            skipped = (
                "(skipped: choose the most likely reading, or failing that the most common claim on the subject, "
                "and state it as an assumption)"
            )
            ask_rule = "" if allow_ask else 'You must now return status "ready".'

        lines = [f"Q: {question}\nA: {answer if answer else skipped}" for question, answer in turns]
        template = AnalysisPrompt.CLARIFY_CLAIM_FR if french else AnalysisPrompt.CLARIFY_CLAIM
        return template.format(
            claim=wrap_untrusted(claim), turns=wrap_untrusted("\n".join(lines) or "(none)"), ask_rule=ask_rule
        )
