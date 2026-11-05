import json
import logging
import re
import secrets
from typing import Any

logger = logging.getLogger(__name__)

# Invisible characters that can hide instructions from a human reader: zero-width, bidi controls, Unicode tags.
_INVISIBLE_CHARS = re.compile("[\u200b\u2060\ufeff\u202a-\u202e\u2066-\u2069\U000e0000-\U000e007f]")
# The labels of our own source format, which a page could use to pose as a separate, highly credible source.
_SOURCE_LABELS = re.compile(
    r"\b(source\s+\d+|title|titre|url|excerpt|extrait|credibility\s+score|index\s+de\s+cr[ée]dibilit[ée])\s*:",
    re.IGNORECASE,
)
# A tripwire for logging and keeping suspect verdicts out of the shared cache. Easy to evade, so never a defence alone.
_INJECTION_MARKERS = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+)?(of\s+)?(the\s+|your\s+)?(previous|prior|above|earlier)\b"
    r"|ignorez\s+(toutes\s+)?(les\s+)?(instructions|consignes)"
    r"|system\s+(note|prompt|message|admin)|(note|message)\s+syst[eè]me"
    r"|veracity_score|credibility\s+score\s*:|\bsource\s+\d+\s*:|you\s+are\s+now\b",
    re.IGNORECASE,
)


def clean_unicode_text(value: Any) -> str:
    """
    Make text safe for JSON responses and PostgreSQL text fields.
    """
    if value is None:
        return ""

    text = value if isinstance(value, str) else str(value)

    text = text.replace("\x00", "")
    text = text.replace("\x1a", "")
    text = _INVISIBLE_CHARS.sub("", text)

    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def flatten_untrusted(value: Any) -> str:
    """One line of external text without our labels, so it cannot imitate the structure of the prompt around it."""
    return " ".join(_SOURCE_LABELS.sub("", clean_unicode_text(value)).split())


def wrap_untrusted(text: str) -> str:
    """Fence untrusted text in a random tag that the text cannot know, and so cannot close."""
    tag = f"data-{secrets.token_hex(4)}"
    return f"<{tag}>\n{text}\n</{tag}>"


def looks_like_injection(*texts: str) -> bool:
    return any(_INJECTION_MARKERS.search(text or "") for text in texts)


def extract_json_candidate(raw_text: str) -> str:
    text = clean_unicode_text(raw_text).strip()

    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        return text[start : end + 1]

    return text


def parse_analysis_response(raw_text: str) -> tuple[int, str]:
    candidate = extract_json_candidate(raw_text)

    try:
        data = json.loads(candidate)
        score = int(float(data["veracity_score"]))
        analysis = clean_unicode_text(data.get("analysis", "No analysis provided"))
        return max(0, min(100, score)), analysis

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning(
            "Malformed analysis JSON from LLM. Falling back to regex extraction. " "Error=%s Raw=%r",
            e,
            raw_text[:2000],
        )

    score_match = re.search(
        r'"veracity_score"\s*:\s*([0-9]+(?:\.\d+)?)',
        candidate,
    )
    # No score means a truncated or blocked reply. Reporting 0 would tell the user the claim is false.
    if not score_match:
        raise ValueError("No veracity score in the analysis response")
    score = int(float(score_match.group(1)))
    score = max(0, min(100, score))

    analysis_match = re.search(
        r'"analysis"\s*:\s*(.*)$',
        candidate,
        flags=re.DOTALL,
    )

    if analysis_match:
        analysis = analysis_match.group(1).strip()
        analysis = analysis.rstrip("}").rstrip(",").strip()

        if analysis.startswith('"'):
            analysis = analysis[1:]

        if analysis.endswith('"'):
            analysis = analysis[:-1]

        analysis = analysis.replace('\\"', '"')
        analysis = analysis.replace("\\n", "\n")
    else:
        analysis = candidate

    analysis = clean_unicode_text(analysis)

    if not analysis:
        analysis = "Analysis was generated, but the response format was malformed."

    return score, analysis
