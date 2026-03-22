"""
JobNexus — job recommendation API (candidates, jobs, matching only).

ASGI app must not be named ``app`` — it collides with the ``app`` package name and
can make uvicorn resolve ``app.main:app`` to the package instead of this instance.
"""
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine, Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    logger.info("Starting JobNexus Recommendation API (backend_v2)...")
    auto_create = os.environ.get("AUTO_CREATE_TABLES", "true").lower() == "true"
    if auto_create:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified (job-domain only)")
    else:
        logger.info("AUTO_CREATE_TABLES=false — skipping create_all")
    yield
    logger.info("Shutting down...")
    await engine.dispose()


fastapi_app = FastAPI(
    title=settings.APP_NAME,
    description="Job recommendation: candidates, jobs, semantic matching",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@fastapi_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@fastapi_app.get("/health")
async def health():
    return {"status": "healthy"}


@fastapi_app.get("/ready")
async def ready():
    return {"status": "ready"}


from app.api.router import api_router  # noqa: E402

fastapi_app.include_router(api_router, prefix="/api/v1")

import app.models.candidate  # noqa: F401, E402
import app.models.job  # noqa: F401, E402
import app.models.match  # noqa: F401, E402
import app.models.job_application  # noqa: F401, E402
