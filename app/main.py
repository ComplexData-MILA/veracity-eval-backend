from fastapi import FastAPI
from app.api.router import router

app = FastAPI(title="Misinformation Mitigation API")

app.include_router(router, prefix="/v1")