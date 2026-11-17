"""Screen for user text that a fact-checker must not act on (HARM_CHECK): a request for help causing harm, or text
that attacks a group of people. Claims and questions about any subject, however false or offensive, pass.

Used before every check and follow-up (harmful), and by the clarifier before it suggests claims for a topic
(harmful or attacks_group). Fails open: on an error the text is treated as safe and the failure is logged.
"""

import json
import logging
from dataclasses import dataclass

from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message as LLMMessage
from app.core.llm.prompts import AnalysisPrompt
from app.core.text_safety import clean_unicode_text, extract_json_candidate, wrap_untrusted

logger = logging.getLogger(__name__)


@dataclass
class Screen:
    harmful: bool = False
    attacks_group: bool = False


async def screen_text(llm: LLMProvider, text: str) -> Screen:
    prompt = AnalysisPrompt.HARM_CHECK.format(text=wrap_untrusted(clean_unicode_text(text)))
    try:
        response = await llm.generate_response(
            [LLMMessage(role="user", content=prompt)], temperature=0.0, json_mode=True
        )
        data = json.loads(extract_json_candidate(response.text or ""))
    except Exception:
        logger.warning("Harm screen failed; treating the text as safe", exc_info=True)
        return Screen()
    if not isinstance(data, dict):
        return Screen()
    return Screen(harmful=data.get("harmful") is True, attacks_group=data.get("attacks_group") is True)
