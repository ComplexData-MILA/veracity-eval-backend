from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.schemas.domain_schema import DomainCreate, DomainRead
from app.services.domain_service import DomainService

router = APIRouter()


@router.post("/", response_model=DomainRead)
async def create_domain(domain_create: DomainCreate, service: DomainService = Depends()):
    domain = service.create_domain(domain_create)
    return DomainRead.model_validate(domain)


@router.get("/{domain_id}", response_model=DomainRead)
async def get_domain(domain_id: UUID, service: DomainService = Depends()):
    domain = service.get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return DomainRead.model_validate(domain)


@router.get("/name/{domain_name}", response_model=DomainRead)
async def get_domain_by_name(domain_name: str, service: DomainService = Depends()):
    domain = service.get_domain_by_name(domain_name)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return DomainRead.model_validate(domain)


@router.put("/{domain_id}", response_model=DomainRead)
async def update_domain(domain_id: UUID, domain_update: DomainCreate, service: DomainService = Depends()):
    domain = service.update_domain(domain_id, domain_update)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return DomainRead.model_validate(domain)


@router.delete("/{domain_id}", response_model=bool)
async def delete_domain(domain_id: UUID, service: DomainService = Depends()):
    success = service.delete_domain(domain_id)
    if not success:
        raise HTTPException(status_code=404, detail="Domain not found")
    return success
