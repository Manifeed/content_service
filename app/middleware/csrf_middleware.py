from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

from app.errors.custom_exceptions import CsrfOriginDeniedError
from app.utils.environment_utils import (
    is_development_environment,
    is_production_like_environment,
)


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def csrf_origin_middleware(request: Request, call_next):
    if _requires_csrf_check(request):
        request_origin = _extract_request_origin(request)
        trusted_origins = _resolve_trusted_origins(request)
        if request_origin is None or request_origin not in trusted_origins:
            exception = CsrfOriginDeniedError()
            return JSONResponse(
                status_code=exception.status_code,
                content=exception.to_payload(),
            )

    return await call_next(request)


def _requires_csrf_check(request: Request) -> bool:
    if request.method.upper() not in UNSAFE_METHODS:
        return False
    path = request.url.path
    return path.startswith("/api/")


def _extract_request_origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return _normalize_origin(origin)

    referer = request.headers.get("referer")
    if referer:
        return _normalize_origin(referer)

    return None


def _resolve_trusted_origins(request: Request) -> set[str]:
    configured_origins = _parse_origin_list(os.getenv("CSRF_TRUSTED_ORIGINS", ""))
    if not configured_origins and is_development_environment():
        configured_origins = _parse_origin_list(os.getenv("CORS_ORIGINS", ""))
    if _trust_request_self_origin():
        configured_origins.add(_request_self_origin(request))
    return configured_origins


def _trust_request_self_origin() -> bool:
    if is_production_like_environment():
        return False
    raw_value = os.getenv("CSRF_TRUST_SELF_ORIGIN")
    if raw_value is not None:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
    for env_var in ("APP_ENV", "ENVIRONMENT", "NODE_ENV"):
        environment = os.getenv(env_var, "").strip().lower()
        if environment in {"prod", "production", "staging"}:
            return False
    return True


def _parse_origin_list(raw_value: str) -> set[str]:
    origins: set[str] = set()
    for raw_origin in raw_value.split(","):
        normalized_origin = _normalize_origin(raw_origin)
        if normalized_origin is not None:
            origins.add(normalized_origin)
    return origins


def _normalize_origin(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        parsed = urlsplit(candidate)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if scheme not in {"http", "https"} or not hostname:
        return None

    netloc = hostname.lower()
    if port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        netloc = f"{netloc}:{port}"
    return f"{scheme}://{netloc}"


def _request_self_origin(request: Request) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip()

    scheme = forwarded_proto or request.url.scheme
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    normalized_origin = _normalize_origin(f"{scheme}://{host}")
    return normalized_origin or str(request.base_url).rstrip("/")
