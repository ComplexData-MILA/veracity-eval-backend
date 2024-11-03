from fastapi import FastAPI
from app.api.router import router
from fastapi.middleware.cors import CORSMiddleware
import logging


app = FastAPI(title="Misinformation Mitigation API")

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


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
