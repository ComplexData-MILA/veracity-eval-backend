"""Split a claim into atomic, self-contained subclaims before fact-checking.

The prompt follows the extractor-segmentor of CAAFC (arXiv 2605.12436): split only when needed, keep unit claims
intact, and keep each subclaim's context. It runs on a small MaaS model; any failure falls back to the claim itself.
"""

import json
import logging
import time
from typing import List, Optional

from app.core.config import settings
from app.core.llm.interfaces import LLMProvider
from app.core.llm.messages import Message
from app.core.llm.prompts import AnalysisPrompt
from app.core.text_safety import clean_unicode_text, extract_json_candidate, wrap_untrusted
from app.services.claim_matching import normalize_claim

logger = logging.getLogger(__name__)

_provider: Optional[LLMProvider] = None


def _get_provider() -> LLMProvider:
    """One provider per process: building one authenticates with Vertex."""
    global _provider
    if _provider is None:
        from app.core.llm.vertex_ai_llama import VertexAILlamaProvider

        _provider = VertexAILlamaProvider(
            settings, model_id=settings.DECOMPOSE_MODEL_NAME, location=settings.DECOMPOSE_LOCATION
        )
        # The client is synchronous, so the limit has to be on the HTTP call; no retries, the fallback is cheap
        _provider.client = _provider.client.with_options(timeout=settings.DECOMPOSE_TIMEOUT_S, max_retries=0)
    return _provider


def parse_subclaims(raw_text: Optional[str], claim: str, max_subclaims: int) -> List[str]:
    """Subclaims from the model's JSON, deduplicated and capped; the claim itself if the reply is unusable."""
    try:
        data = json.loads(extract_json_candidate(raw_text or ""))
        items = data.get("subclaims") if isinstance(data, dict) else data
    except (json.JSONDecodeError, TypeError, ValueError):
        items = None
    subclaims, seen = [], set()
    for item in items if isinstance(items, list) else []:
        text = " ".join(clean_unicode_text(item).split()) if isinstance(item, str) else ""
        key = normalize_claim(text)
        if text and key not in seen:
            seen.add(key)
            subclaims.append(text[:500])
    return subclaims[:max_subclaims] or [claim]


async def decompose(claim: str, provider: Optional[LLMProvider] = None) -> List[str]:
    max_subclaims = settings.DECOMPOSE_MAX_SUBCLAIMS
    prompt = AnalysisPrompt.DECOMPOSE_CLAIM.format(max_subclaims=max_subclaims, statement=wrap_untrusted(claim))
    started = time.perf_counter()
    try:
        response = await (provider or _get_provider()).generate_response(
            [Message(role="user", content=prompt)], temperature=0.0
        )
        subclaims = parse_subclaims(response.text, claim, max_subclaims)
    except Exception as e:
        logger.error(f"Claim decomposition failed, checking the claim whole: {str(e)}", exc_info=True)
        subclaims = [claim]
    logger.info(f"Decompose timings: llm_ms={round((time.perf_counter() - started) * 1000)} n={len(subclaims)}")
    return subclaims
