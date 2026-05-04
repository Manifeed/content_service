import os
from typing import List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analytics.analysis_router import analysis_router
from shared_backend.errors.exception_handlers import register_exception_handlers
from app.middleware.csrf_middleware import csrf_origin_middleware
from app.rss.rss_router import rss_public_router
from app.sources.router import admin_sources_router, user_sources_router
from shared_backend.schemas.internal.service_schema import InternalServiceHealthRead
from shared_backend.utils.environment_utils import is_development_environment
from shared_backend.utils.logging_utils import (
    configure_service_logging,
    create_request_logging_middleware,
)


def _parse_cors_origins() -> Tuple[List[str], bool]:
    raw_origins = os.getenv("CORS_ORIGINS", "")
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if "*" in origins:
        raise RuntimeError("CORS_ORIGINS cannot contain '*' when credentials are enabled")
    if origins:
        return origins, True
    if is_development_environment():
        return ["http://localhost:8080", "http://localhost:3000"], True
    return [], False


def create_app() -> FastAPI:
    configure_service_logging("content-service")
    app = FastAPI(
        title="Manifeed Content Service",
    )

    cors_origins, allow_credentials = _parse_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.middleware("http")(
        create_request_logging_middleware(
            service_name="content-service",
            route_class="internal-content",
        )
    )
    app.middleware("http")(csrf_origin_middleware)

    app.include_router(rss_public_router)
    app.include_router(admin_sources_router)
    app.include_router(user_sources_router)
    app.include_router(analysis_router)

    @app.get("/internal/health", response_model=InternalServiceHealthRead)
    def read_internal_health() -> InternalServiceHealthRead:
        return InternalServiceHealthRead(service="content-service", status="ok")

    register_exception_handlers(app)

    return app


app = create_app()
