from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from uuid import UUID

from app.models.database.claim import ClaimStatus
from app.models.domain.user import User
from app.schemas.claim_schema import ClaimCreate, ClaimList, ClaimRead, ClaimStatusUpdate
from app.services.claim_service import ClaimService
from app.core.exceptions import NotFoundException, NotAuthorizedException

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("/", response_model=ClaimRead, status_code=status.HTTP_201_CREATED, summary="Create a new claim")
async def create_claim(
    data: ClaimCreate,
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    claim_service: ClaimService = Depends(),
):
    """Create a new claim for the authenticated user."""
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")

    claim = await claim_service.create_claim(user_id=user.id, claim_text=data.claim_text, context=data.context)
    return ClaimRead.model_validate(claim)


@router.get("/", response_model=ClaimList, summary="List user claims")
async def list_claims(
    status: Optional[ClaimStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    claim_service: ClaimService = Depends(),
):
    """List claims for the authenticated user with pagination."""
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")

    claims, total = await claim_service.list_user_claims(user_id=user.id, status=status, limit=limit, offset=offset)
    return ClaimList(items=[ClaimRead.model_validate(c) for c in claims], total=total, limit=limit, offset=offset)


@router.get("/{claim_id}", response_model=ClaimRead, summary="Get claim by ID")
async def get_claim(
    claim_id: UUID,
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    claim_service: ClaimService = Depends(),
):
    """Get a specific claim by ID."""
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")

    try:
        claim = await claim_service.get_claim(claim_id=claim_id, user_id=user.id)
        return ClaimRead.model_validate(claim)
    except (NotFoundException, NotAuthorizedException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{claim_id}/status", response_model=ClaimRead, summary="Update claim status")
async def update_claim_status(
    claim_id: UUID,
    data: ClaimStatusUpdate,
    # current_data: Tuple[User, Auth0Session] = Depends(get_current_user_and_session),
    claim_service: ClaimService = Depends(),
):
    """Update a claim's status."""
    # fake user for now
    user = User(id=UUID("00000000-0000-0000-0000-000000000000"), email="bob@test.com")

    try:
        claim = await claim_service.update_claim_status(
            claim_id=claim_id, status=ClaimStatus(data.status), user_id=user.id
        )
        return ClaimRead.model_validate(claim)
    except (NotFoundException, NotAuthorizedException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
