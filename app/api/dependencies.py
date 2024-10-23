from fastapi import Depends

from app.services.user_service import UserService


async def get_user_service(user_service: UserService = Depends(UserService)) -> UserService:
    return user_service
