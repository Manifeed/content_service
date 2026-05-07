from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import check_content_database_ready
from app.routers.internal_content_router import internal_content_router
from app.services.readiness_service import check_qdrant_ready, check_source_search_embedder_ready

from shared_backend.errors.exception_handlers import register_exception_handlers
from shared_backend.security.internal_service_auth import validate_internal_service_token_configuration
from shared_backend.schemas.internal.service_schema import InternalServiceHealthRead
from shared_backend.utils.logging_utils import (
    configure_service_logging,
    create_request_logging_middleware,
)


@asynccontextmanager
async def _app_lifespan(_: FastAPI):
    validate_internal_service_token_configuration()
    check_source_search_embedder_ready()
    yield


def create_app() -> FastAPI:
    configure_service_logging("content-service")
    app = FastAPI(title="Manifeed Content Service", lifespan=_app_lifespan)
    app.middleware("http")(
        create_request_logging_middleware(
            service_name="content-service",
            route_class="internal-content",
        )
    )
    app.include_router(internal_content_router)
    register_exception_handlers(app)

    @app.get("/internal/health", response_model=InternalServiceHealthRead)
    def read_internal_health() -> InternalServiceHealthRead:
        return InternalServiceHealthRead(service="content-service", status="ok")

    @app.get("/internal/ready", response_model=InternalServiceHealthRead)
    def read_internal_ready() -> InternalServiceHealthRead:
        validate_internal_service_token_configuration()
        check_content_database_ready()
        check_qdrant_ready()
        check_source_search_embedder_ready()
        return InternalServiceHealthRead(service="content-service", status="ready")

    return app


app = create_app()
