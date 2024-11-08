# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import router
from fastapi.middleware.cors import CORSMiddleware
from app.core.auth.auth0_middleware import Auth0Middleware
from app.services.user_service import UserService
from app.repositories.implementations.user_repository import UserRepository
from app.db.session import AsyncSessionLocal
import logging

formatter = logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
logging.getLogger("fastapi").setLevel(logging.WARNING)


async def get_user_service():
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        return UserService(user_repo)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("API Starting up")
    user_service = await get_user_service()
    app.state.auth_middleware = Auth0Middleware(user_service)
    yield
    logging.info("API Shutting down")


app = FastAPI(
    title="Misinformation Mitigation API",
    response_model_exclude_unset=True,
    response_validation=False,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://misinformation-mitigation-ui.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(router, prefix="/v1")
