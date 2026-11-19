from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.accounts import router as accounts_router
from app.api.routes.scans import router as scans_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import get_logger

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting SafeScale API")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")
    yield
    await engine.dispose()
    logger.info("SafeScale API shut down")


app = FastAPI(
    title="SafeScale API",
    description="On-Demand Availability platform — reduces cloud HA overspend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts_router, prefix="/api/v1")
app.include_router(scans_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "safescale"}


def run() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
