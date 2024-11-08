from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID

from app.api.dependencies import get_user_service, get_current_user
from app.core.exceptions import NotFoundException
from app.models.domain.user import User
from app.schemas.user_schema import UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserRead:
    """Get the currently authenticated user's information."""
    return UserRead.model_validate(current_user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: UUID, current_user: User = Depends(get_current_user), user_service: UserService = Depends(get_user_service)
) -> UserRead:
    """Get user by ID. Only allowed for the current user or admins."""
    try:
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this user's information"
            )

        user = await user_service.get_user(user_id)
        return UserRead.model_validate(user)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get user: {str(e)}")


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    current_user: User = Depends(get_current_user), user_service: UserService = Depends(get_user_service)
) -> UserRead:
    """Update the currently authenticated user's information."""
    try:
        updated_user = await user_service.update_user(current_user)
        return UserRead.model_validate(updated_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update user: {str(e)}"
        )
