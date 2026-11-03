"""LLM-free checks that decide whether a cached claim's analysis can be reused for a new claim.

Dense embeddings score "X", "not X" and "X in 2015" as near-identical, so similarity only selects
candidates. Reuse is decided by:
  - mutual entailment from a multilingual NLI cross-encoder (A entails B and B entails A means the
    same assertion; Kuhn et al., "Semantic Uncertainty", ICLR 2023) -> the verdict is reused;
  - claims that are identical once their numbers are masked, but whose numbers differ -> only the
    gathered sources are reused and the verdict is recomputed.
"""

import asyncio
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

from app.core.config import settings

TIER_FULL = "full"
TIER_EVIDENCE = "evidence"

# Digits, decimals, thousands separators ("," "." or a space before exactly three digits, as in French
# "1 000") and an optional percent sign. Digits glued to letters or hyphens (COVID-19, 5G, G7) are part
# of a name, not a quantity.
_NUMBER = re.compile(r"(?<![\w-])\d+(?:[.,]\d+|[   ]\d{3}(?!\d))*(?:\s?%)?(?![\w-])")
# Punctuation, except "." and "," between two digits (decimal and thousands separators)
_PUNCT = re.compile(r"(?<!\d)[.,]|[.,](?!\d)|[^\w\s.,%]")


def normalize_claim(text: str) -> str:
    """Case-, accent-form-, punctuation- and whitespace-insensitive form of a claim."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(_PUNCT.sub(" ", text).split())


def claim_hash(text: str) -> str:
    return hashlib.sha256(normalize_claim(text).encode()).hexdigest()


def _canonical_number(raw: str) -> str:
    """Same canonical form for EN and FR spellings: 1,000 / 1 000 -> 1000; 2.5 / 2,5 -> 2.5."""
    percent = raw.rstrip().endswith("%")
    groups = re.split(r"[.,   ]", raw.rstrip("%   "))
    if len(groups) > 1 and all(len(g) == 3 for g in groups[1:]):
        value = "".join(groups)
    elif len(groups) == 2:
        value = f"{groups[0]}.{groups[1]}"
    else:
        value = "".join(groups)
    return value + ("%" if percent else "")


def extract_numbers(text: str) -> List[str]:
    return sorted(_canonical_number(m) for m in _NUMBER.findall(unicodedata.normalize("NFKC", text)))


def mask_numbers(text: str) -> str:
    return normalize_claim(_NUMBER.sub(" N ", unicodedata.normalize("NFKC", text)))


def is_number_variant(claim_a: str, claim_b: str) -> bool:
    """Same wording apart from different numbers, e.g. "legalized in 2018" vs "legalized in 2015"."""
    return extract_numbers(claim_a) != extract_numbers(claim_b) and mask_numbers(claim_a) == mask_numbers(claim_b)


@dataclass
class MatchDecision:
    tier: Optional[str]
    reason: str
    entailment: Optional[float] = None


def decide(entailment: Optional[float], number_variant: bool) -> MatchDecision:
    if entailment is not None and entailment >= settings.SEMCACHE_ENTAIL_T:
        return MatchDecision(TIER_FULL, "mutual-entailment", entailment)
    if number_variant:
        return MatchDecision(TIER_EVIDENCE, "number-variant", entailment)
    return MatchDecision(None, "not-equivalent", entailment)


class ClaimVerifier:
    """Multilingual NLI cross-encoder, loaded once per process and run off the event loop."""

    _model = None
    _entail_idx: int = 0

    @classmethod
    def _load(cls):
        if cls._model is None:
            from sentence_transformers import CrossEncoder

            from app.services.verifier_trim import ensure_trimmed_model

            source = settings.SEMCACHE_VERIFIER_MODEL
            path = ensure_trimmed_model(source) if settings.SEMCACHE_VERIFIER_TRIM else source
            cls._model = CrossEncoder(path, device="cpu")
            labels = {v.lower(): int(k) for k, v in cls._model.model.config.id2label.items()}
            cls._entail_idx = labels["entailment"]
        return cls._model

    @classmethod
    def _mutual_entailment(cls, pairs: Sequence[Tuple[str, str]]) -> List[float]:
        model = cls._load()
        both = list(pairs) + [(b, a) for a, b in pairs]
        logits = np.asarray(model.predict(both, batch_size=32))
        probs = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs /= probs.sum(axis=1, keepdims=True)
        n = len(pairs)
        return [float(min(probs[i][cls._entail_idx], probs[n + i][cls._entail_idx])) for i in range(n)]

    async def warm_up(self) -> None:
        """Load the model and run one inference so the first cache lookup doesn't pay ~15 s of loading."""
        await self.mutual_entailment([("Warm-up claim.", "Warm-up claim.")])

    async def mutual_entailment(self, pairs: Sequence[Tuple[str, str]]) -> List[float]:
        if not pairs:
            return []
        return await asyncio.get_running_loop().run_in_executor(None, self._mutual_entailment, pairs)
