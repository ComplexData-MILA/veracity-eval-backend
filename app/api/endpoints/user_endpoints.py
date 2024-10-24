from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID

from app.api.dependencies import get_user_service
from app.core.exceptions import NotFoundException
from app.models.domain.user import User
from app.schemas.user_schema import UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead, summary="Get current user")
async def get_current_user() -> UserRead:
    """Get the currently authenticated user's information."""
    # fake user for now
    user = User(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        email="bob@test.com",
    )

    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead, summary="Get user by ID")
async def get_user(user_id: UUID, user_service: UserService = Depends(get_user_service)) -> UserRead:
    try:
        user = await user_service.get_user(user_id)
        return UserRead.model_validate(user)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
