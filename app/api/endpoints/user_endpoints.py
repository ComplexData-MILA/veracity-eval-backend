from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.schemas.user_schema import UserCreate, UserRead
from app.services.user_service import UserService
from app.models.domain.user import User

router = APIRouter()


@router.post("/", response_model=UserRead)
def create_user(user_create: UserCreate, service: UserService = Depends()) -> UserRead:
    user: User = service.create_user(user_create)
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, service: UserService = Depends()) -> UserRead:
    user: User = service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)
