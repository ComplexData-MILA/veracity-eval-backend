import json
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from uuid import UUID

from app.api.dependencies import get_analysis_service
from app.models.domain.user import User
from app.services.analysis_service import AnalysisService
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.schemas.analysis_schema import AnalysisRead, AnalysisList
from app.core.exceptions import NotFoundException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/{analysis_id}", response_model=AnalysisRead, summary="Get analysis by ID")
async def get_analysis(
    analysis_id: UUID,
    include_sources: bool = Query(False),
    include_feedback: bool = Query(False),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisRead:
    """
    Get a completed analysis by ID.

    Parameters:
    - include_sources: Include the sources used in the analysis
    - include_feedback: Include user feedback on the analysis
    """
    try:
        analysis = await analysis_service.get_analysis(
            analysis_id=analysis_id, include_sources=include_sources, include_feedback=include_feedback
        )
        return AnalysisRead.model_validate(analysis)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/claim/{claim_id}/stream", response_class=StreamingResponse, summary="Stream claim analysis")
async def stream_claim_analysis(
    claim_id: UUID,
    # current_data: tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    analysis_orchestrator: AnalysisOrchestrator = Depends(get_analysis_service),
) -> StreamingResponse:
    """
    Stream the analysis process for a claim in real-time.

    The stream will include:
    1. Source gathering status
    2. LLM analysis progress
    3. Final analysis results
    """
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")

    async def event_generator():
        try:
            async for event in analysis_orchestrator.analyze_claim_stream(claim_id=claim_id, user_id=user.id):
                if isinstance(event, dict):
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/claim/{claim_id}", response_model=List[AnalysisRead], summary="Get claim analyses")
async def get_claim_analyses(
    claim_id: UUID,
    include_sources: bool = Query(False),
    include_feedback: bool = Query(False),
    # current_data: tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> List[AnalysisRead]:
    """
    Get all analyses for a claim.
    There might be multiple analyses if the claim was re-analyzed.
    """
    # fake user for now
    analyses = await analysis_service.get_claim_analyses(
        claim_id=claim_id, include_sources=include_sources, include_feedback=include_feedback
    )
    return [AnalysisRead.model_validate(a) for a in analyses]


@router.get("/claim/{claim_id}/latest", response_model=AnalysisRead, summary="Get latest claim analysis")
async def get_latest_claim_analysis(
    claim_id: UUID,
    include_sources: bool = Query(False),
    include_feedback: bool = Query(False),
    # current_data: tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisRead:
    """
    Get the most recent analysis for a claim.
    """
    analysis = await analysis_service.get_latest_claim_analysis(
        claim_id=claim_id, include_sources=include_sources, include_feedback=include_feedback
    )
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis found for this claim")
    return AnalysisRead.model_validate(analysis)


@router.post("/claim/{claim_id}/reanalyze", response_class=StreamingResponse, summary="Request claim reanalysis")
async def reanalyze_claim(
    claim_id: UUID,
    # current_data: tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    analysis_orchestrator: AnalysisOrchestrator = Depends(get_analysis_service),
) -> StreamingResponse:
    """
    Request a new analysis for an existing claim.
    Useful when new information might be available.
    """
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")

    async def event_generator():
        try:
            async for event in analysis_orchestrator.reanalyze_claim_stream(claim_id=claim_id, user_id=user.id):
                if isinstance(event, dict):
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/", response_model=AnalysisList, summary="Get recent analyses")
async def get_recent_analyses(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_sources: bool = Query(False),
    # current_data: tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisList:
    """
    Get recent analyses with pagination.
    Results are ordered by creation date (newest first).
    """
    items, total = await analysis_service.get_recent_analyses(
        limit=limit, offset=offset, include_sources=include_sources
    )
    return AnalysisList(items=[AnalysisRead.model_validate(a) for a in items], total=total, limit=limit, offset=offset)
