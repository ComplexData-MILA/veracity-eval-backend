from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import router
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import logging

from app.core.auth.auth0_middleware import Auth0Middleware

formatter = logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
logging.getLogger("fastapi").setLevel(logging.WARNING)

auth0_middleware = Auth0Middleware(domain=settings.AUTH0_DOMAIN, audience=settings.AUTH0_AUDIENCE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("API Starting up")
    yield
    # Shutdown
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
