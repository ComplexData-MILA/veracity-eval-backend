import hashlib
import json
import logging
from dataclasses import dataclass, field
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
# Freshness is the reader's: a UI check and a batch run accept entries up to different ages
_LIVE = (
    "language = :language AND params_hash = :params_hash AND NOT invalidated "
    "AND created_at > now() - make_interval(hours => :max_age_hours)"
)


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
    max_age_hours: int = field(default_factory=lambda: settings.SEMCACHE_UI_TTL_HOURS)
    # Whole-claim verdict cache: batch runs only. Interactive checks reuse subclaim evidence, never a verdict.
    claim: bool = False
    # NLI (paraphrase) matching for whole claims; no path turns it on, so batch reuse is exact-text only
    claim_nli: bool = False


_SUBCLAIM_COLUMNS = "id, subclaim_text, subclaim_hash, search_id, created_at"


def is_subclaim_match(subclaim: str, cached: str, entailment: Optional[float]) -> bool:
    """Reuse a subclaim's evidence only when both assert the same fact; a different number is a different fact."""
    return (
        entailment is not None and entailment >= settings.SEMCACHE_ENTAIL_T and not is_number_variant(subclaim, cached)
    )


@dataclass
class SubclaimHit:
    entry_id: UUID
    search_id: UUID
    subclaim_text: str
    cached_at: datetime
    similarity: float
    reason: str
    entailment: Optional[float] = None
    sources: list = field(default_factory=list)


def _subclaim_hit(row, similarity: float, reason: str, entailment: Optional[float] = None) -> SubclaimHit:
    return SubclaimHit(
        entry_id=row.id,
        search_id=row.search_id,
        subclaim_text=row.subclaim_text,
        cached_at=row.created_at,
        similarity=similarity,
        reason=reason,
        entailment=entailment,
    )


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
    def policy(bypass_cache: bool = False, eval_mode: bool = False, batch: bool = False) -> CachePolicy:
        """Eval runs never touch the cache; 'Re-check' skips the read but refreshes the entries.

        UI checks reuse subclaim evidence up to SEMCACHE_UI_TTL_HOURS old. Batch runs (benchmarks) also replay exact
        repeats of a whole claim, and reuse entries up to SEMCACHE_BATCH_TTL_HOURS old.
        """
        if eval_mode or not settings.semantic_cache_enabled:
            return CachePolicy(read=False, write=False)
        max_age = settings.SEMCACHE_BATCH_TTL_HOURS if batch else settings.SEMCACHE_UI_TTL_HOURS
        return CachePolicy(read=not bypass_cache, write=True, max_age_hours=max_age, claim=batch)

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
        if settings.CLAIM_DECOMPOSITION_ENABLED:
            # Kept out of the hash when off, so turning the feature on never invalidates today's entries
            prompts += [
                settings.DECOMPOSE_MODEL_NAME,
                AnalysisPrompt.DECOMPOSE_CLAIM,
                AnalysisPrompt.SUBCLAIM_EVIDENCE_NOTE,
                AnalysisPrompt.SUBCLAIM_EVIDENCE_NOTE_FR,
                AnalysisPrompt.SUBCLAIM_VERDICT_RULES,
                AnalysisPrompt.SUBCLAIM_VERDICT_RULES_FR,
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

    async def exact_lookup(
        self, claim_text: str, language: str, params_hash: str, max_age_hours: int
    ) -> Optional[CacheHit]:
        """Same claim up to case, punctuation and whitespace: no embedding or model call needed."""
        row = (
            await self._session.execute(
                text(
                    f"SELECT {_ENTRY_COLUMNS} FROM semantic_cache_entries "
                    f"WHERE claim_hash = :claim_hash AND {_LIVE} ORDER BY created_at DESC LIMIT 1"
                ),
                {
                    "claim_hash": claim_hash(claim_text),
                    "language": language,
                    "params_hash": params_hash,
                    "max_age_hours": max_age_hours,
                },
            )
        ).first()
        return self._to_hit(row, TIER_FULL, 1.0, "exact") if row else None

    async def candidates(
        self, embedding: List[float], language: str, params_hash: str, max_age_hours: int
    ) -> List[Tuple[object, float]]:
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
                    "max_age_hours": max_age_hours,
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
        await self._session.execute(text("DELETE FROM semantic_cache_entries WHERE id = :id"), {"id": entry_id})
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
        retain = timedelta(hours=max(settings.SEMCACHE_UI_TTL_HOURS, settings.SEMCACHE_BATCH_TTL_HOURS))
        # A fresh run of the same claim supersedes the older entry
        await self._session.execute(
            text(
                """
                DELETE FROM semantic_cache_entries
                WHERE claim_hash = :claim_hash AND language = :language AND params_hash = :params_hash
                """
            ),
            {"claim_hash": key, "language": language, "params_hash": params_hash},
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
                "expires_at": now + retain,
                "now": now,
            },
        )
        # Drop entries too old for any path, then the oldest beyond the size cap
        await self._session.execute(
            text("DELETE FROM semantic_cache_entries WHERE created_at < :oldest"), {"oldest": now - retain}
        )
        await self._session.execute(
            text(
                """
                DELETE FROM semantic_cache_entries WHERE id IN (
                    SELECT id FROM semantic_cache_entries ORDER BY created_at DESC OFFSET :max_entries
                )
                """
            ),
            {"max_entries": settings.SEMCACHE_MAX_ENTRIES},
        )
        await self._session.commit()

    # ---------- subclaim cache: one entry per atomic subclaim, pointing at the search that gathered its evidence ----------

    @staticmethod
    def subclaim_params_hash(language: str, preferred_domains: Optional[List[str]], search_provider: str) -> str:
        """Only what changes the evidence a search returns; LLM and prompt changes keep cached evidence usable."""
        payload = {
            "language": language,
            "preferred_domains": sorted(preferred_domains or []),
            "search_provider": search_provider,
            "embedding_model": settings.SEMCACHE_EMBEDDING_MODEL,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    async def embed_many(self, texts: List[str]) -> List[List[float]]:
        from vertexai.language_models import TextEmbeddingInput

        model = _get_embedding_model()
        result = await model.get_embeddings_async([TextEmbeddingInput(t, "SEMANTIC_SIMILARITY") for t in texts])
        return [r.values for r in result]

    async def subclaim_lookup(
        self, texts: List[str], embeddings: List[List[float]], language: str, params_hash: str, max_age_hours: int
    ) -> List[Optional[SubclaimHit]]:
        """A cached entry per subclaim when one asserts the same thing, with its sources; None where there is none."""
        params = {"language": language, "params_hash": params_hash, "max_age_hours": max_age_hours}
        rows = (
            await self._session.execute(
                text(
                    f"SELECT {_SUBCLAIM_COLUMNS} FROM subclaim_cache_entries "
                    f"WHERE subclaim_hash = ANY(:hashes) AND {_LIVE} ORDER BY created_at DESC"
                ),
                {**params, "hashes": [claim_hash(t) for t in texts]},
            )
        ).all()
        by_hash = {}
        for row in rows:
            by_hash.setdefault(row.subclaim_hash, row)
        hits: List[Optional[SubclaimHit]] = [
            _subclaim_hit(by_hash[claim_hash(t)], 1.0, "exact") if claim_hash(t) in by_hash else None for t in texts
        ]

        if settings.SEMCACHE_NLI_ENABLED:
            candidates = []
            for i, embedding in enumerate(embeddings):
                if hits[i] is not None:
                    continue
                rows = (
                    await self._session.execute(
                        text(
                            f"""
                            SELECT {_SUBCLAIM_COLUMNS}, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                            FROM subclaim_cache_entries
                            WHERE {_LIVE}
                            ORDER BY embedding <=> CAST(:embedding AS vector), created_at DESC
                            LIMIT :top_k
                            """
                        ),
                        {**params, "embedding": str(embedding), "top_k": settings.SEMCACHE_TOP_K},
                    )
                ).all()
                candidates += [(i, row) for row in rows if row.similarity >= settings.SEMCACHE_T_RECALL]
            if candidates:
                # One verifier pass over every subclaim's candidates
                scores = await self._verifier.mutual_entailment(
                    [(texts[i], row.subclaim_text) for i, row in candidates]
                )
                for (i, row), entailment in zip(candidates, scores):
                    reuse = is_subclaim_match(texts[i], row.subclaim_text, entailment)
                    logger.info(
                        f"Subclaim cache candidate: similarity={row.similarity:.4f} entailment={entailment:.4f} "
                        f"reuse={reuse}"
                    )
                    if reuse and hits[i] is None:
                        hits[i] = _subclaim_hit(row, row.similarity, "mutual-entailment", entailment)

        found = [hit for hit in hits if hit is not None]
        if found:
            sources = (
                await self._session.execute(
                    text(
                        "SELECT search_id, url, title, snippet, domain_id, content, credibility_score FROM sources "
                        "WHERE search_id = ANY(:search_ids) ORDER BY created_at, id"
                    ),
                    {"search_ids": [hit.search_id for hit in found]},
                )
            ).all()
            for hit in found:
                hit.sources = [source for source in sources if source.search_id == hit.search_id]
            await self._session.execute(
                text("UPDATE subclaim_cache_entries SET hit_count = hit_count + 1 WHERE id = ANY(:ids)"),
                {"ids": [hit.entry_id for hit in found]},
            )
            await self._session.commit()
        return hits

    async def store_subclaims(
        self, entries: List[Tuple[str, List[float], UUID]], language: str, params_hash: str
    ) -> None:
        """Store (subclaim, embedding, search_id) entries; a fresh search of the same subclaim supersedes the old one."""
        now = datetime.now(UTC)
        retain = timedelta(hours=max(settings.SEMCACHE_UI_TTL_HOURS, settings.SEMCACHE_BATCH_TTL_HOURS))
        for subclaim, embedding, search_id in entries:
            key = claim_hash(subclaim)
            await self._session.execute(
                text(
                    "DELETE FROM subclaim_cache_entries "
                    "WHERE subclaim_hash = :subclaim_hash AND language = :language AND params_hash = :params_hash"
                ),
                {"subclaim_hash": key, "language": language, "params_hash": params_hash},
            )
            await self._session.execute(
                text(
                    """
                    INSERT INTO subclaim_cache_entries
                        (id, subclaim_text, subclaim_hash, language, params_hash, embedding, search_id,
                         expires_at, created_at, updated_at)
                    VALUES
                        (:id, :subclaim_text, :subclaim_hash, :language, :params_hash, CAST(:embedding AS vector),
                         :search_id, :expires_at, :now, :now)
                    """
                ),
                {
                    "id": uuid4(),
                    "subclaim_text": subclaim,
                    "subclaim_hash": key,
                    "language": language,
                    "params_hash": params_hash,
                    "embedding": str(embedding),
                    "search_id": search_id,
                    "expires_at": now + retain,
                    "now": now,
                },
            )
        await self._session.execute(
            text("DELETE FROM subclaim_cache_entries WHERE created_at < :oldest"), {"oldest": now - retain}
        )
        await self._session.execute(
            text(
                """
                DELETE FROM subclaim_cache_entries WHERE id IN (
                    SELECT id FROM subclaim_cache_entries ORDER BY created_at DESC OFFSET :max_entries
                )
                """
            ),
            {"max_entries": settings.SUBCLAIM_CACHE_MAX_ENTRIES},
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
