import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm.prompts import AnalysisPrompt
from app.services.claim_matching import (
    TIER_EVIDENCE,
    TIER_FULL,
    ClaimVerifier,
    claim_hash,
    decide,
    is_number_variant,
)

logger = logging.getLogger(__name__)

_embedding_model = None

_ENTRY_COLUMNS = "id, source_analysis_id, claim_text, veracity_score, analysis_text, created_at"
_LIVE = "language = :language AND params_hash = :params_hash AND expires_at > now() AND NOT invalidated"


def _get_embedding_model():
    """Lazily initialise the Vertex embedding model with the mounted service account."""
    global _embedding_model
    if _embedding_model is None:
        import vertexai
        from google.oauth2 import service_account
        from vertexai.language_models import TextEmbeddingModel

        credentials = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        vertexai.init(
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.SEMCACHE_EMBEDDING_LOCATION,
            credentials=credentials,
        )
        _embedding_model = TextEmbeddingModel.from_pretrained(settings.SEMCACHE_EMBEDDING_MODEL)
    return _embedding_model


@dataclass
class CachePolicy:
    read: bool
    write: bool


@dataclass
class CacheHit:
    tier: str
    entry_id: UUID
    source_analysis_id: UUID
    claim_text: str
    veracity_score: float
    analysis_text: str
    cached_at: datetime
    similarity: float
    reason: str = ""
    entailment: Optional[float] = None


class SemanticCacheService:
    """Cache of completed analyses in Postgres: exact match, pgvector candidates, then an NLI verifier."""

    def __init__(self, session: AsyncSession, verifier: Optional[ClaimVerifier] = None):
        self._session = session
        self._verifier = verifier or ClaimVerifier()

    @staticmethod
    def policy(bypass_cache: bool = False, eval_mode: bool = False) -> CachePolicy:
        """Eval runs never touch the cache; 'Re-check' skips the read but refreshes the entry."""
        if eval_mode or not settings.semantic_cache_enabled:
            return CachePolicy(read=False, write=False)
        return CachePolicy(read=not bypass_cache, write=True)

    @staticmethod
    def params_hash(language: str, default: bool, preferred_domains: Optional[List[str]]) -> str:
        """Everything besides the claim text that changes the analysis. Prompt/model changes start a new cache."""
        prompts = [
            AnalysisPrompt.ORCHESTRATOR_PROMPT,
            AnalysisPrompt.ORCHESTRATOR_PROMPT_FR,
            AnalysisPrompt.GET_VERACITY,
            AnalysisPrompt.GET_VERACITY_EX,
            AnalysisPrompt.GET_VERACITY_FR,
        ]
        payload = {
            "language": language,
            "default": default,
            "preferred_domains": sorted(preferred_domains or []),
            "model": settings.LLAMA_MODEL_NAME,
            "prompts": hashlib.sha256("\n".join(prompts).encode()).hexdigest(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    async def embed(self, claim_text: str) -> List[float]:
        from vertexai.language_models import TextEmbeddingInput

        model = _get_embedding_model()
        result = await model.get_embeddings_async([TextEmbeddingInput(claim_text, "SEMANTIC_SIMILARITY")])
        return result[0].values

    @staticmethod
    def _to_hit(row, tier: str, similarity: float, reason: str, entailment: Optional[float] = None) -> CacheHit:
        return CacheHit(
            tier=tier,
            entry_id=row.id,
            source_analysis_id=row.source_analysis_id,
            claim_text=row.claim_text,
            veracity_score=row.veracity_score,
            analysis_text=row.analysis_text,
            cached_at=row.created_at,
            similarity=similarity,
            reason=reason,
            entailment=entailment,
        )

    async def exact_lookup(self, claim_text: str, language: str, params_hash: str) -> Optional[CacheHit]:
        """Same claim up to case, punctuation and whitespace: no embedding or model call needed."""
        row = (
            await self._session.execute(
                text(
                    f"SELECT {_ENTRY_COLUMNS} FROM semantic_cache_entries "
                    f"WHERE claim_hash = :claim_hash AND {_LIVE} ORDER BY created_at DESC LIMIT 1"
                ),
                {"claim_hash": claim_hash(claim_text), "language": language, "params_hash": params_hash},
            )
        ).first()
        return self._to_hit(row, TIER_FULL, 1.0, "exact") if row else None

    async def candidates(self, embedding: List[float], language: str, params_hash: str) -> List[Tuple[object, float]]:
        """Nearest live entries above the recall floor; similarity alone never decides reuse."""
        rows = (
            await self._session.execute(
                text(
                    f"""
                    SELECT {_ENTRY_COLUMNS}, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                    FROM semantic_cache_entries
                    WHERE {_LIVE}
                    ORDER BY embedding <=> CAST(:embedding AS vector), created_at DESC
                    LIMIT :top_k
                    """
                ),
                {
                    "embedding": str(embedding),
                    "language": language,
                    "params_hash": params_hash,
                    "top_k": settings.SEMCACHE_TOP_K,
                },
            )
        ).all()
        return [(row, row.similarity) for row in rows if row.similarity >= settings.SEMCACHE_T_RECALL]

    async def select_hit(self, claim_text: str, candidates: List[Tuple[object, float]]) -> Optional[CacheHit]:
        """Verify candidates; a full (verdict) reuse beats an evidence-only reuse."""
        if not candidates:
            return None
        scores = await self._verifier.mutual_entailment([(claim_text, row.claim_text) for row, _ in candidates])
        best = None
        for (row, similarity), entailment in zip(candidates, scores):
            decision = decide(entailment, is_number_variant(claim_text, row.claim_text))
            logger.info(
                f"Semantic cache candidate: similarity={similarity:.4f} entailment={entailment:.4f} "
                f"tier={decision.tier} reason={decision.reason}"
            )
            if decision.tier == TIER_FULL:
                return self._to_hit(row, TIER_FULL, similarity, decision.reason, entailment)
            if decision.tier == TIER_EVIDENCE and best is None:
                best = self._to_hit(row, TIER_EVIDENCE, similarity, decision.reason, entailment)
        return best

    async def rollback(self) -> None:
        await self._session.rollback()

    async def invalidate(self, entry_id: UUID) -> None:
        await self._session.execute(
            text("UPDATE semantic_cache_entries SET invalidated = true, updated_at = now() WHERE id = :id"),
            {"id": entry_id},
        )
        await self._session.commit()

    async def record_hit(self, entry_id: UUID) -> None:
        await self._session.execute(
            text("UPDATE semantic_cache_entries SET hit_count = hit_count + 1 WHERE id = :id"), {"id": entry_id}
        )
        await self._session.commit()

    async def store(
        self,
        embedding: List[float],
        claim_text: str,
        language: str,
        params_hash: str,
        analysis_id: UUID,
        veracity_score: float,
        analysis_text: str,
    ) -> None:
        now = datetime.now(UTC)
        key = claim_hash(claim_text)
        # A fresh run of the same claim supersedes the older entry
        await self._session.execute(
            text(
                """
                UPDATE semantic_cache_entries SET invalidated = true, updated_at = :now
                WHERE claim_hash = :claim_hash AND language = :language AND params_hash = :params_hash
                """
            ),
            {"now": now, "claim_hash": key, "language": language, "params_hash": params_hash},
        )
        await self._session.execute(
            text(
                """
                INSERT INTO semantic_cache_entries
                    (id, claim_text, claim_hash, language, params_hash, embedding, source_analysis_id,
                     veracity_score, analysis_text, expires_at, created_at, updated_at)
                VALUES
                    (:id, :claim_text, :claim_hash, :language, :params_hash, CAST(:embedding AS vector),
                     :analysis_id, :veracity_score, :analysis_text, :expires_at, :now, :now)
                """
            ),
            {
                "id": uuid4(),
                "claim_text": claim_text,
                "claim_hash": key,
                "language": language,
                "params_hash": params_hash,
                "embedding": str(embedding),
                "analysis_id": analysis_id,
                "veracity_score": veracity_score,
                "analysis_text": analysis_text,
                "expires_at": now + timedelta(hours=settings.SEMCACHE_TTL_HOURS),
                "now": now,
            },
        )
        await self._session.commit()

    @staticmethod
    def hit_metadata(hit: Optional[CacheHit]) -> dict:
        """Fields added to analysis_complete so the UI can show the cached-result disclaimer."""
        if hit is None:
            return {"cached": False}
        return {"cached": True, "cache_tier": hit.tier, "cached_at": hit.cached_at.isoformat()}


def split_for_replay(analysis_text: str, chunk_size: int = 40) -> Tuple[str, ...]:
    return tuple(analysis_text[i : i + chunk_size] for i in range(0, len(analysis_text), chunk_size))
