from datetime import datetime, UTC
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
from wordcloud import WordCloud, STOPWORDS
import json
import plotly.graph_objects as go
import logging

from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
import plotly.express as px
import pandas as pd
import numpy as np

from app.models.database.models import ClaimStatus
from app.models.domain.claim import Claim
from app.repositories.implementations.claim_repository import ClaimRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.services.analysis_orchestrator import AnalysisOrchestrator

from app.core.exceptions import NotFoundException, NotAuthorizedException

from nltk.corpus import stopwords

import nltk
import asyncio
from concurrent.futures import ThreadPoolExecutor

nltk.download("stopwords")

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=1)


class ClaimService:
    def __init__(self, claim_repository: ClaimRepository, analysis_repository: AnalysisRepository):
        self._claim_repo = claim_repository
        self._analysis_repo = analysis_repository

    async def create_claim(
        self,
        user_id: UUID,
        claim_text: str,
        context: str,
        language: str,
        batch_user_id: str = None,
        batch_post_id: str = None,
    ) -> Claim:
        """Create a new claim."""
        now = datetime.now(UTC)
        claim = Claim(
            id=uuid4(),
            user_id=user_id,
            claim_text=claim_text,
            context=context,
            language=language,
            status=ClaimStatus.pending,
            created_at=now,
            updated_at=now,
            batch_user_id=batch_user_id,
            batch_post_id=batch_post_id,
        )

        return await self._claim_repo.create(claim)

    async def update_claim_status(self, claim_id: UUID, status: ClaimStatus, user_id: UUID) -> Claim:
        """Update claim status."""
        claim = await self.get_claim(claim_id, user_id)
        claim.status = status
        claim.updated_at = datetime.now(UTC)
        return await self._claim_repo.update(claim)

    async def update_claim_embedding(self, claim_id: UUID, embedding: List[float], user_id: UUID) -> Claim:
        """Update claim status."""
        claim = await self.get_claim(claim_id, user_id)
        claim.embedding = embedding
        claim.updated_at = datetime.now(UTC)
        return await self._claim_repo.update(claim)

    async def get_claim(self, claim_id: UUID, user_id: Optional[UUID] = None) -> Claim:
        """Get a claim and optionally verify ownership."""
        claim = await self._claim_repo.get(claim_id)
        if not claim:
            raise NotFoundException("Claim not found")

        if user_id and claim.user_id != user_id:
            raise NotAuthorizedException("Not authorized to access this claim")

        return claim

    async def list_user_claims(
        self, user_id: UUID, status: Optional[ClaimStatus] = None, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Claim], int]:
        """List claims for a user with pagination."""
        return await self._claim_repo.get_user_claims(user_id=user_id, status=status, limit=limit, offset=offset)

    async def list_time_bound_claims(
        self, start_date: datetime, end_date: datetime, language: str = "english"
    ) -> List[Claim]:
        """List claims for a specific date range."""
        return await self._claim_repo.get_claims_in_date_range(
            start_date=start_date, end_date=end_date, language=language
        )

    async def generate_word_cloud(self, claims: List[Claim]) -> str:
        def _heavy_word_cloud_math(claims):
            claim_texts = list(map(lambda claim: claim.claim_text, claims))

            if len(claim_texts) <= 0:
                wordcloud = WordCloud(background_color="white", colormap="rainbow", margin=0).generate("Empty")

                image = wordcloud.to_array()
                fig = go.Figure(go.Image(z=image))

                fig.update_layout(
                    xaxis=dict(showgrid=False, zeroline=False, visible=False),
                    yaxis=dict(showgrid=False, zeroline=False, visible=False),
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    margin=dict(l=20, r=20, t=20, b=20),
                )
                fig_json = fig.to_json()
                graph = json.loads(fig_json)
                return graph

            french_stopwords = set(stopwords.words("french"))
            custom_stopwords = french_stopwords.union(STOPWORDS)

            text = " ".join(claim_texts)
            wordcloud = WordCloud(
                background_color="white", colormap="rainbow", margin=0, stopwords=custom_stopwords
            ).generate(text)

            image = wordcloud.to_array()
            fig = go.Figure(go.Image(z=image))

            fig.update_layout(
                xaxis=dict(showgrid=False, zeroline=False, visible=False),
                yaxis=dict(showgrid=False, zeroline=False, visible=False),
                paper_bgcolor="white",
                plot_bgcolor="white",
                margin=dict(l=20, r=20, t=20, b=20),
            )
            fig_json = fig.to_json()
            graph = json.loads(fig_json)

            logger.debug("generated word cloud picture")

            return graph

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, _heavy_word_cloud_math, claims)
        return result

    async def generate_clustering_graph(self, claims: List[Claim], num_clusters: int) -> str:
        def _heavy_clustering_math(claims, num_clusters):
            claim_embed = list(map(lambda claim: claim.embedding, filter(lambda c: c.embedding is not None, claims)))

            if len(claim_embed) > 5000:
                logging.info("claim embed greater than 6000")
                import random

                random.seed(42)
                claim_embed = random.sample(claim_embed, 5000)

            if len(claim_embed) < 3:
                fig = go.Figure()
                fig.update_layout(
                    title=None,  # Remove title
                    xaxis_title=None,  # Remove x-axis title
                    yaxis_title=None,  # Remove y-axis title
                    xaxis=dict(showticklabels=False),  # Hide x-axis numbers
                    yaxis=dict(showticklabels=False),  # Hide y-axis numbers
                    template="plotly_white",
                )
                fig_json = fig.to_json()
                graph = json.loads(fig_json)
                return graph
            else:
                # Reduce embedding size
                X = np.array(claim_embed, dtype=np.float32)
                if len(claim_embed) < 30:
                    X_embedded = TSNE(
                        n_components=2, learning_rate="auto", init="random", perplexity=len(claim_embed) - 1
                    ).fit_transform(X)
                else:
                    X_embedded = TSNE(n_components=2, learning_rate="auto", init="random", perplexity=30).fit_transform(
                        X
                    )

                kmeans = KMeans(n_clusters=num_clusters, random_state=0, n_init="auto").fit(X_embedded)

                df = pd.DataFrame(X_embedded, columns=["x", "y"])
                df["cluster"] = kmeans.labels_  # Assign KMeans labels

                df["claim_text"] = [
                    (c.claim_text[:100] + "...") if len(c.claim_text) > 100 else c.claim_text
                    for c in claims
                    if c.embedding is not None
                ]
                # claim.claim_text for claim in claims if claim.embedding is not None

                fig = px.scatter(
                    df,
                    x="x",
                    y="y",
                    color=df["cluster"].astype(str),
                    title=None,
                    labels={"cluster": "Cluster", "claim_text": "Claim text"},
                    color_discrete_sequence=px.colors.qualitative.Set1,  # Custom color scheme
                    template="plotly_white",
                    hover_data={
                        "x": False,  # Remove x-axis data from hover
                        "y": False,  # Remove y-axis data from hover
                        "cluster": True,  # Rename the color to 'cluster'
                        "claim_text": True,  # Show claim_text
                    },
                )

                fig.update_layout(
                    xaxis_title=None,
                    yaxis_title=None,
                    xaxis=dict(showticklabels=False),
                    yaxis=dict(showticklabels=False),
                    legend_title="Cluster",  # Set custom legend title
                )

                fig_json = fig.to_json()
                graph = json.loads(fig_json)

                return graph

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, _heavy_clustering_math, claims, num_clusters)
        return result

    async def create_claims_batch(self, claims: List[Claim], user_id: str) -> List[Claim]:
        # Map ClaimCreate + user_id → Claim DB objects
        now = datetime.now(UTC)
        claim_models = [
            Claim(
                id=uuid4(),
                user_id=user_id,
                claim_text=c.claim_text,
                context=c.context,
                language=c.language,
                batch_user_id=c.batch_user_id,
                batch_post_id=c.batch_post_id,
                status=ClaimStatus.pending,
                created_at=now,
                updated_at=now,
                # Optional: Add default status, timestamps if needed
            )
            for c in claims
        ]

        return await self._claim_repo.insert_many(claim_models)

    async def process_claims_batch_async(
        self,
        created_claims,
        user_id: str,
        analysis_orchestrator: AnalysisOrchestrator,
    ):
        successes = []
        failures = []

        for claim in created_claims:
            try:
                result = await analysis_orchestrator.analyze_claim_direct(claim.id, user_id)
                analysis = result.get("analysis")

                searches = analysis.searches or []
                flat_sources = [source for search in searches for source in (search.sources or [])]

                seen_urls = set()
                unique_sources = []
                for source in flat_sources:
                    if source.url not in seen_urls:
                        unique_sources.append(source)
                        seen_urls.add(source.url)

                valid_scores = [
                    source.credibility_score for source in unique_sources if source.credibility_score is not None
                ]

                avg_source_cred = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

                successes.append(
                    {
                        "claim_id": str(claim.id),
                        "analysis_id": str(analysis.id),
                        "batch_user_id": claim.batch_user_id,
                        "batch_post_id": claim.batch_post_id,
                        "veracity_score": analysis.veracity_score,
                        "average_source_credibility": avg_source_cred,
                        "num_sources": len(valid_scores),
                    }
                )

            except Exception as e:
                logging.exception(f"Analysis failed for claim {claim.id}")
                failures.append(
                    {
                        "claim_id": str(claim.id),
                        "status": "error",
                        "message": str(e),
                    }
                )

        # Optionally, store results somewhere (DB, cache, file, etc.)
        logging.info(f"Batch completed: {len(successes)} successes, {len(failures)} failures")

    async def get_analysis_results_for_claim_ids(self, claim_ids: List[UUID]):
        successes = []
        failures = []
        pending = []

        for claim_id in claim_ids:
            try:
                # You may need to adjust this based on how you load a claim/analysis
                claim = await self._claim_repo.get(claim_id)
                if claim is None:
                    failures.append(
                        {
                            "claim_id": str(claim_id),
                            "batch_user_id": "None",
                            "batch_post_id": "None",
                            "status": "error",
                            "message": "claim ID not in the database",
                        }
                    )
                    continue
                analysis = await self._analysis_repo.get_latest_by_claim(
                    claim_id=claim_id, include_searches=True, include_sources=True
                )

                if analysis is None or analysis.status in ("pending", "processing"):
                    pending.append(
                        {
                            "claim_id": str(claim_id),
                            "batch_user_id": str(claim.batch_user_id) if claim.batch_user_id else "None",
                            "batch_post_id": str(claim.batch_post_id) if claim.batch_post_id else "None",
                            "status": "incomplete",
                            "message": "analysis not started, waiting",
                        }
                    )
                    continue

                if analysis.status in ("failed", "disputed"):
                    failures.append(
                        {
                            "claim_id": str(claim_id),
                            "batch_user_id": str(claim.batch_user_id) if claim.batch_user_id else "None",
                            "batch_post_id": str(claim.batch_post_id) if claim.batch_post_id else "None",
                            "status": "failed",
                            "message": f"analysis not completed, in state {analysis.status}",
                        }
                    )
                    continue

                searches = analysis.searches or []
                flat_sources = [source for search in searches for source in (search.sources or [])]

                seen_urls = set()
                unique_sources = []
                for source in flat_sources:
                    if source.url not in seen_urls:
                        unique_sources.append(source)
                        seen_urls.add(source.url)

                valid_scores = [
                    source.credibility_score for source in unique_sources if source.credibility_score is not None
                ]

                avg_source_cred = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

                successes.append(
                    {
                        "claim_id": str(claim_id),
                        "analysis_id": str(analysis.id),
                        "batch_user_id": claim.batch_user_id,
                        "batch_post_id": claim.batch_post_id,
                        "veracity_score": analysis.veracity_score,
                        "average_source_credibility": avg_source_cred,
                        "num_sources": len(valid_scores),
                    }
                )
            except Exception as e:
                failures.append(
                    {
                        "claim_id": str(claim.id),
                        "batch_user_id": claim.batch_user_id if claim.batch_user_id else "None",
                        "batch_post_id": claim.batch_post_id if claim.batch_post_id else "None",
                        "status": "error",
                        "message": str(e),
                    }
                )
                continue

        return {"successes": successes, "failures": failures, "pending": pending}
