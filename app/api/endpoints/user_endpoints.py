from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_user_service
from app.core.exceptions import UserAlreadyExistsError
from app.services.user_service import UserService
from app.schemas.user_schema import UserCreate, UserRead

router = APIRouter()


@router.post("/", response_model=UserRead)
async def create_user(user_data: UserCreate, user_service: UserService = Depends(get_user_service)):
    try:
        user = await user_service.create_user(user_data)
        return UserRead.model_validate(user)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, user_service: UserService = Depends(get_user_service)):
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)
