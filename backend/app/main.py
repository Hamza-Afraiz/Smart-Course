import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from temporalio.client import Client

from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SmartCourse API starting up — env: %s", settings.app_env)
    try:
        app.state.temporal_client = await asyncio.wait_for(
            Client.connect(settings.temporal_host, namespace="default"),
            timeout=5.0,
        )
        logger.info("Temporal client connected — %s", settings.temporal_host)
    except Exception as e:
        logger.warning("Temporal unavailable — publish will return 503: %s", e)
        app.state.temporal_client = None
    yield
    await engine.dispose()
    logger.info("SmartCourse API shut down — connections closed")


app = FastAPI(
    title="SmartCourse API",
    description="Backend for the SmartCourse intelligent learning platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    # tighten this to specific origins in production
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Exception Handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback — this is the only place a 500 should originate
    logger.exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"},
    )

# ── Routers ───────────────────────────────────────────────────────────────────

from app.routers.auth import router as auth_router
from app.routers.courses import router as courses_router
from app.routers.enrollments import router as enrollments_router
from app.routers.users import router as users_router

app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(users_router, prefix="/api/v1/users")
app.include_router(courses_router, prefix="/api/v1/courses")
app.include_router(enrollments_router, prefix="/api/v1/enrollments")

# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}
