from fastapi import APIRouter, Depends
import logging

from app.api.dependencies import get_claim_extraction_service, get_current_user
from app.models.domain.user import User
from app.schemas.claim_extraction_schema import (
    ClaimExtractionRequest,
    ClaimExtractionResponse,
    ExtractedStatement,
)
from app.services.claim_extraction_service import ClaimExtractionService

router = APIRouter(prefix="/claims", tags=["claims"])
logger = logging.getLogger(__name__)


@router.post(
    "/extract",
    response_model=ClaimExtractionResponse,
    summary="Extract verifiable statements from free text",
)
async def extract_claims(
    data: ClaimExtractionRequest,
    current_user: User = Depends(get_current_user),
    extraction_service: ClaimExtractionService = Depends(get_claim_extraction_service),
) -> ClaimExtractionResponse:
    """Extract self-contained, verifiable statements from free text.

    Nothing is persisted here: the user confirms which statement they meant, and
    only then is a claim created through POST /claims/. Consequently this route
    injects no repository and no database session, so it cannot create a claim
    row or count against the monthly claim limit.
    """
    result = await extraction_service.extract_statements(text=data.text, language=data.language)

    return ClaimExtractionResponse(
        statements=[ExtractedStatement(id=f"s{index}", text=text) for index, text in enumerate(result.statements)],
        reason=result.reason,
        language=data.language,
    )
