"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.api.config import Settings
from backend.api.db.database import async_engine
from backend.api.routers import analysis, coaching, sessions, tracks, trends


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    # Startup: connection pool is created lazily by SQLAlchemy
    yield
    # Shutdown: dispose the async engine connection pool
    await async_engine.dispose()


settings = Settings()

app = FastAPI(
    title="Cataclysm API",
    description="Motorsport telemetry analysis and AI coaching",
    version="0.1.0",
    lifespan=lifespan,
)

# -- Middleware (order matters: last added = first executed) ------------------

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Routers -----------------------------------------------------------------

app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(analysis.router, prefix="/api/sessions", tags=["analysis"])
app.include_router(coaching.router, prefix="/api/coaching", tags=["coaching"])
app.include_router(trends.router, prefix="/api/trends", tags=["trends"])
app.include_router(tracks.router, prefix="/api/tracks", tags=["tracks"])


# -- Health ------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple health-check response."""
    return {"status": "ok"}
