import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter
from app.api.v1 import auth, jobs, projects

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Code BEFORE yield runs on startup.
    Code AFTER yield runs on shutdown.
    """
    # --- STARTUP ---
    logger.info("Starting up SQL Optimizer API...")

    # Ensure MinIO bucket exists (lazy init — MinIO must be reachable by now)
    try:
        from app.services.storage import minio_service
        minio_service.ensure_bucket_exists()
    except Exception as e:
        # Log but don't crash — worker will fail gracefully if MinIO is down
        logger.warning(f"MinIO bucket init failed (service may be starting): {e}")

    logger.info("Startup complete.")
    yield

    # --- SHUTDOWN ---
    logger.info("Shutting down SQL Optimizer API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Attach limiter state and its 429 handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── GLOBAL ERROR HANDLERS ────────────────────────────────────────────────────
#
# FastAPI / Pydantic V2 by default returns validation errors as:
#   { "detail": [ { "type": "...", "loc": [...], "msg": "...", "input": "..." } ] }
#
# That raw array of objects is not a string — if it reaches a React component
# that renders `{error}` directly, React throws "Objects are not valid as a
# React child".  The handlers below normalise EVERY error path into the safe:
#   { "detail": "<human-readable string>" }
# shape, so the frontend always receives a renderable value.
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Flatten Pydantic V2 validation errors into a single human-readable string.

    Input (default FastAPI behaviour):
        { "detail": [ { "type": "uuid_parsing", "loc": ["body","project_id"],
                        "msg": "...", "input": "bad-value" } ] }

    Output (after this handler):
        { "detail": "project_id: Input should be a valid UUID, ..." }
    """
    errors = exc.errors()
    readable_parts: list[str] = []

    for err in errors:
        # Build a dotted field path, skipping noise tokens like "body" / "query"
        loc_parts = [
            str(part)
            for part in err.get("loc", [])
            if part not in ("body", "query", "path", "header")
        ]
        field = ".".join(loc_parts) if loc_parts else "request"
        msg = err.get("msg") or err.get("type") or "Validation error"
        readable_parts.append(f"{field}: {msg}")

    detail = " | ".join(readable_parts) if readable_parts else "Invalid request."
    logger.warning(
        "RequestValidationError on %s %s — %s",
        request.method, request.url.path, detail,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": detail},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """
    Re-raise HTTPException in the standard format but log it for observability.

    FastAPI's built-in handler already does this; we override solely to add
    structured logging so 4xx errors from business logic are visible in the
    Docker logs without crashing the server.
    """
    logger.warning(
        "HTTPException %s on %s %s — %s",
        exc.status_code, request.method, request.url.path, exc.detail,
    )
    # Ensure detail is always a string (guards against accidental object detail)
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Catch-all for any unhandled exception.

    Logs the full traceback for debugging while returning a sanitised 500
    response — never leaking internal implementation details (stack traces,
    DB query strings, etc.) to the client.
    """
    logger.error(
        "Unhandled exception on %s %s\n%s",
        request.method, request.url.path, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )



# ── CORS ─────────────────────────────────────────────────────────────────────
# Use configured origins if available, otherwise fallback to localhost:3000
allowed_origins = (
    [str(o) for o in settings.BACKEND_CORS_ORIGINS]
    if settings.BACKEND_CORS_ORIGINS
    else ["http://localhost:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ROUTERS ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,     prefix=f"{settings.API_V1_STR}/auth",     tags=["auth"])
app.include_router(projects.router, prefix=f"{settings.API_V1_STR}/projects", tags=["projects"])
app.include_router(jobs.router,     prefix=f"{settings.API_V1_STR}/jobs",     tags=["jobs"])


# ── HEALTH ENDPOINTS ──────────────────────────────────────────────────────────
@app.get("/", tags=["health"])
def root():
    return {"message": "SQL Optimizer API is running", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health_check():
    """Liveness probe — used by Docker/K8s to check if the app is alive."""
    return {"status": "ok"}