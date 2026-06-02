import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def clean_unicode_text(value: Any) -> str:
    """
    Make text safe for JSON responses and PostgreSQL text fields.
    """
    if value is None:
        return ""

    text = value if isinstance(value, str) else str(value)

    text = text.replace("\x00", "")
    text = text.replace("\x1a", "")

    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


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
        score = int(float(data.get("veracity_score", 0)))
        analysis = clean_unicode_text(data.get("analysis", "No analysis provided"))
        return max(0, min(100, score)), analysis

    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(
            "Malformed analysis JSON from LLM. Falling back to regex extraction. " "Error=%s Raw=%r",
            e,
            raw_text[:2000],
        )

    score_match = re.search(
        r'"veracity_score"\s*:\s*([0-9]+(?:\.\d+)?)',
        candidate,
    )
    score = int(float(score_match.group(1))) if score_match else 0
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
