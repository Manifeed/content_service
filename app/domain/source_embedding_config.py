from __future__ import annotations

import os

from shared_backend.domain.source_embedding_config import (
    FIXED_SOURCE_EMBEDDING_MODEL_NAME,
    resolve_qdrant_api_key,
    resolve_qdrant_collection_name,
    resolve_qdrant_url,
    resolve_source_embedding_dimensions,
    resolve_source_embedding_model_name,
)

DEFAULT_EMBEDDING_SERVICE_URL = "http://127.0.0.1:8000"
DEFAULT_SOURCE_SEARCH_DIMENSIONS = 1024
DEFAULT_SOURCE_SEARCH_RECENCY_HALFLIFE_DAYS = 7.0


def resolve_embedding_service_url() -> str:
    inference_url = os.getenv("EMBEDDING_SERVICE_URL", "").strip()
    if not inference_url:
        return DEFAULT_EMBEDDING_SERVICE_URL
    return inference_url.rstrip("/")


def resolve_embedding_service_api_key() -> str:
    api_key = os.getenv("EMBEDDING_SERVICE_API_KEY", "").strip()
    if api_key:
        return api_key
    raise RuntimeError("EMBEDDING_SERVICE_API_KEY is required")


def resolve_source_search_dimensions() -> int:
    parsed = resolve_source_embedding_dimensions()
    if parsed is not None:
        return parsed
    return DEFAULT_SOURCE_SEARCH_DIMENSIONS


def resolve_source_search_recency_halflife_days() -> float:
    raw_value = os.getenv("SOURCE_SEARCH_RECENCY_HALFLIFE_DAYS", "").strip()
    if raw_value:
        try:
            parsed = float(raw_value)
        except ValueError:
            parsed = DEFAULT_SOURCE_SEARCH_RECENCY_HALFLIFE_DAYS
        if parsed > 0:
            return parsed
    return DEFAULT_SOURCE_SEARCH_RECENCY_HALFLIFE_DAYS
