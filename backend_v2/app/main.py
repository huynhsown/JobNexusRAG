"""
JobNexus — job recommendation API (candidates, jobs, matching only).

ASGI app must not be named ``app`` — it collides with the ``app`` package name and
can make uvicorn resolve ``app.main:app`` to the package instead of this instance.
"""
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine, Base
from app.core.schema_bootstrap import bootstrap_schema
from app.core.security import install_api_key_middleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    logger.info("Starting JobNexus Recommendation API (backend_v2)...")
    auto_create = os.environ.get("AUTO_CREATE_TABLES", "true").lower() == "true"
    if auto_create:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await bootstrap_schema(conn, logger)
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


def custom_openapi():
    if fastapi_app.openapi_schema:
        return fastapi_app.openapi_schema

    openapi_schema = get_openapi(
        title=fastapi_app.title,
        version=fastapi_app.version,
        description=fastapi_app.description,
        routes=fastapi_app.routes,
    )

    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Authorization header: Bearer <token>",
    }
    security_schemes["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": settings.API_KEY_HEADER,
        "description": f"API key header: {settings.API_KEY_HEADER}",
    }

    protected_prefixes = tuple(
        p.strip() for p in settings.API_KEY_PROTECTED_PREFIXES.split(",") if p.strip()
    ) or ("/api/",)
    for path, path_item in openapi_schema.get("paths", {}).items():
        if not any(path.startswith(prefix) for prefix in protected_prefixes):
            continue
        for method in ("get", "post", "put", "patch", "delete", "options", "head"):
            operation = path_item.get(method)
            if not operation:
                continue
            # Require both schemes so Swagger includes both headers when authorized.
            operation["security"] = [{"ApiKeyAuth": [], "BearerAuth": []}]

    fastapi_app.openapi_schema = openapi_schema
    return fastapi_app.openapi_schema


fastapi_app.openapi = custom_openapi

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_api_key_middleware(fastapi_app, settings, logger)


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
