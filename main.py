import logging
import os
from logging.config import dictConfig
from typing import List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analytics.analysis_router import analysis_router
from shared_backend.errors.exception_handlers import register_exception_handlers
from app.middleware.csrf_middleware import csrf_origin_middleware
from app.rss.rss_router import rss_public_router
from app.sources.router import admin_sources_router, user_sources_router
from app.utils.environment_utils import is_development_environment
from shared_backend.schemas.internal.service_schema import InternalServiceHealthRead


class ExcludeHealthcheckAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 5:
            return True

        method = args[1]
        path = args[2]
        if method == "GET" and path == "/openapi.json":
            return False
        return True


def _configure_app_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "exclude_healthcheck_access": {
                    "()": ExcludeHealthcheckAccessFilter,
                }
            },
            "formatters": {
                "app_default": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    "fmt": "%(levelprefix)s %(message)s",
                    "use_colors": None,
                }
            },
            "handlers": {
                "app_default": {
                    "class": "logging.StreamHandler",
                    "formatter": "app_default",
                    "stream": "ext://sys.stderr",
                },
                "uvicorn_access": {
                    "class": "logging.StreamHandler",
                    "formatter": "app_default",
                    "stream": "ext://sys.stdout",
                    "filters": ["exclude_healthcheck_access"],
                },
            },
            "loggers": {
                "app": {
                    "handlers": ["app_default"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["uvicorn_access"],
                    "level": "INFO",
                    "propagate": False,
                }
            },
        }
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
    _configure_app_logging()
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
