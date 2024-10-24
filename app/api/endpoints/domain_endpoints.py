from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID
from app.api.dependencies import get_domain_service
from app.services.domain_service import DomainService
from app.schemas.domain_schema import DomainCreate, DomainUpdate, DomainRead
from app.core.utils.url import normalize_domain_name, is_valid_domain
from app.core.exceptions import NotFoundException, ValidationError

router = APIRouter(prefix="/domains", tags=["domains"])


@router.post(
    "/",
    response_model=DomainRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new domain",
)
async def create_domain(
    domain: DomainCreate, domain_service: DomainService = Depends(get_domain_service)
) -> DomainRead:
    try:
        if not is_valid_domain(domain.domain_name):
            raise ValidationError("Invalid domain name format")

        result = await domain_service.create_domain(
            domain_name=domain.domain_name,
            credibility_score=domain.credibility_score,
            is_reliable=domain.is_reliable,
            description=domain.description,
        )
        return DomainRead.model_validate(result)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/lookup/{domain_name}", response_model=DomainRead, summary="Lookup domain by name")
async def lookup_domain(
    domain_name: str,
    create_if_missing: bool = Query(False),
    domain_service: DomainService = Depends(get_domain_service),
) -> DomainRead:
    try:
        normalized_name = normalize_domain_name(domain_name)
        if not is_valid_domain(normalized_name):
            raise ValidationError("Invalid domain name format")

        if create_if_missing:
            domain, _ = await domain_service.get_or_create_domain(normalized_name)
        else:
            domain = await domain_service.get_by_name(normalized_name)
            if not domain:
                raise NotFoundException("Domain not found")

        return DomainRead.model_validate(domain)
    except (ValidationError, NotFoundException) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{domain_id}", response_model=DomainRead, summary="Get domain by ID")
async def get_domain(domain_id: UUID, domain_service: DomainService = Depends(get_domain_service)) -> DomainRead:
    try:
        domain = await domain_service.get_domain(domain_id)
        return DomainRead.model_validate(domain)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{domain_id}", response_model=DomainRead, summary="Update domain")
async def update_domain(
    domain_id: UUID, update_data: DomainUpdate, domain_service: DomainService = Depends(get_domain_service)
) -> DomainRead:
    try:
        domain = await domain_service.update_domain(
            domain_id=domain_id,
            credibility_score=update_data.credibility_score,
            is_reliable=update_data.is_reliable,
            description=update_data.description,
        )
        return DomainRead.model_validate(domain)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
