from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.schemas.claim_schema import ClaimCreate, ClaimRead
from app.services.claim_service import ClaimService
from app.models.domain.claim import Claim

router = APIRouter()


@router.post("/", response_model=ClaimRead)
def create_claim(claim_create: ClaimCreate, service: ClaimService = Depends()) -> ClaimRead:
    claim: Claim = service.create_claim(claim_create)
    return ClaimRead.model_validate(claim)


@router.get("/{claim_id}", response_model=ClaimRead)
def get_claim(claim_id: UUID, service: ClaimService = Depends()) -> ClaimRead:
    claim: Claim = service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return ClaimRead.model_validate(claim)
