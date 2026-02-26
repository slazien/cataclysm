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
from backend.api.routers import analysis, auth, coaching, equipment, sessions, tracks, trends

logger = logging.getLogger(__name__)


async def _reload_sessions_from_disk() -> int:
    """Re-process CSV files from the data directory into the in-memory store.

    This ensures sessions survive backend restarts.  The DB keeps metadata
    (for the session list) but telemetry lives in memory only — this fills
    the gap by re-processing the CSV files that are already on disk.
    """
    from pathlib import Path

    from backend.api.services.pipeline import process_file_path
    from backend.api.services.session_store import get_session

    data_dir = Path(settings.session_data_dir)
    if not data_dir.is_dir():
        logger.info("Session data dir %s does not exist, skipping reload", data_dir)
        return 0

    csv_files = sorted(data_dir.rglob("*.csv"))
    logger.info("Found %d CSV file(s) in %s", len(csv_files), data_dir)
    loaded = 0
    for csv_path in csv_files:
        try:
            result = await process_file_path(csv_path)
            sid = str(result["session_id"])
            if get_session(sid) is not None:
                loaded += 1
        except Exception:
            logger.warning("Failed to reload %s on startup", csv_path.name, exc_info=True)

    return loaded


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    logging.basicConfig(level=logging.INFO)

    # Startup: initialise coaching persistence and reload cached reports
    from backend.api.services.coaching_store import init_coaching_dir, load_persisted_reports

    init_coaching_dir(settings.coaching_data_dir)
    n = load_persisted_reports()
    if n:
        logger.info("Loaded %d persisted coaching report(s)", n)

    from backend.api.services.equipment_store import (
        init_equipment_dir,
        load_persisted_profiles,
        load_persisted_session_equipment,
    )

    init_equipment_dir(settings.equipment_data_dir)
    n_eq = load_persisted_profiles()
    n_se = load_persisted_session_equipment()
    if n_eq or n_se:
        logger.info("Loaded %d equipment profile(s), %d session assignment(s)", n_eq, n_se)

    # Reload CSV session data into memory so GET endpoints don't 404
    n_sessions = await _reload_sessions_from_disk()
    if n_sessions:
        logger.info("Reloaded %d session(s) from disk", n_sessions)

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
    # Equipment endpoints: mutable (CRUD)
    ("/api/equipment", "no-cache"),
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

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(analysis.router, prefix="/api/sessions", tags=["analysis"])
app.include_router(coaching.router, prefix="/api/coaching", tags=["coaching"])
app.include_router(equipment.router, prefix="/api/equipment", tags=["equipment"])
app.include_router(trends.router, prefix="/api/trends", tags=["trends"])
app.include_router(tracks.router, prefix="/api/tracks", tags=["tracks"])


# -- Health ------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple health-check response."""
    return {"status": "ok"}
