"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from backend.api.config import Settings
from backend.api.routers import analysis, coaching, sessions, tracks, trends

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    # Startup: initialise coaching persistence and reload cached reports
    from backend.api.services.coaching_store import init_coaching_dir, load_persisted_reports

    init_coaching_dir(settings.coaching_data_dir)
    n = load_persisted_reports()
    if n:
        logger.info("Loaded %d persisted coaching report(s)", n)

    yield

    # Shutdown: clear in-memory store
    from backend.api.services.session_store import clear_all

    clear_all()


load_dotenv()  # Populate os.environ from .env before reading settings
settings = Settings()

app = FastAPI(
    title="Cataclysm API",
    description="Motorsport telemetry analysis and AI coaching",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)


# -- Cache-Control middleware --------------------------------------------------

# Route prefix -> Cache-Control header value
_CACHE_RULES: list[tuple[str, str]] = [
    # Coaching endpoints: mutable (generated on demand)
    ("/api/coaching", "no-cache"),
    # Session list: mutable (changes on upload/delete)
    ("/api/sessions/upload", "no-cache"),
    # Analysis sub-routes: immutable once computed for a session
    ("/api/sessions/", "max-age=60"),
    # Trends: immutable for a given set of sessions
    ("/api/trends", "max-age=60"),
    # Tracks: static reference data
    ("/api/tracks", "max-age=3600"),
]


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Set Cache-Control headers based on the request path and method."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip WebSocket connections — BaseHTTPMiddleware cannot handle them
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        response = await call_next(request)

        # Only apply to successful GET responses without an existing header
        if request.method != "GET" or response.status_code >= 400:
            return response
        if "cache-control" in response.headers:
            return response

        path = request.url.path
        for prefix, value in _CACHE_RULES:
            if path.startswith(prefix):
                response.headers["Cache-Control"] = value
                break
        else:
            # Default: no-cache for any unmatched GET
            response.headers["Cache-Control"] = "no-cache"

        return response


# -- Exception handlers --------------------------------------------------------


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions.

    Logs the full traceback server-side but returns a safe generic message
    to the client (no internal details leaked).
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return 422 for ValueError (bad input data that passed validation)."""
    logger.warning("ValueError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )


# -- Middleware (order matters: last added = first executed) ------------------

app.add_middleware(CacheControlMiddleware)
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
