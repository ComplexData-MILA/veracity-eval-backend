from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.schemas.analysis_schema import AnalysisCreate, AnalysisRead
from app.services.analysis_service import AnalysisService

router = APIRouter()


@router.post("/", response_model=AnalysisRead)
async def create_analysis(analysis_create: AnalysisCreate, service: AnalysisService = Depends()):
    analysis = service.create_analysis(analysis_create)
    return AnalysisRead.model_validate(analysis)


@router.get("/{analysis_id}", response_model=AnalysisRead)
async def get_analysis(analysis_id: UUID, service: AnalysisService = Depends()):
    analysis = service.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisRead.model_validate(analysis)
