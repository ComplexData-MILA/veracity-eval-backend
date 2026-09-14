import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message as LLMMessage
from app.core.llm.prompts import AnalysisPrompt
from app.core.text_safety import clean_unicode_text, extract_json_candidate

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


@dataclass
class ExtractionResult:
    """Outcome of a claim extraction attempt."""

    statements: List[str] = field(default_factory=list)
    reason: str = REASON_OK


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
        return template.format(text=text)
