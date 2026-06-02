from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_current_user
from app.models.domain.user import User
from app.services.openfake_service import verify_media_with_openfake

router = APIRouter(prefix="/media")


@router.post("/verify")
async def verify_media(
    file: UploadFile = File(...),
    # Only logged-in users can call this endpoint
    current_user: User = Depends(get_current_user),
):
    return await verify_media_with_openfake(file)
