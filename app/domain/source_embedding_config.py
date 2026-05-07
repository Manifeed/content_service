from __future__ import annotations

import os

FIXED_SOURCE_EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
DEFAULT_EMBEDDING_SERVICE_URL = "http://127.0.0.1:8000"
DEFAULT_QDRANT_URL = "http://qdrant:6333"
DEFAULT_QDRANT_COLLECTION = "article_embeddings"
DEFAULT_SOURCE_SEARCH_DIMENSIONS = 1024
DEFAULT_SOURCE_SEARCH_RECENCY_HALFLIFE_DAYS = 14.0


def resolve_source_embedding_model_name() -> str:
    return FIXED_SOURCE_EMBEDDING_MODEL_NAME


def resolve_source_embedding_dimensions() -> int | None:
    raw_value = os.getenv("SOURCE_EMBEDDING_DIMENSIONS", "").strip()
    if not raw_value:
        return None
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def resolve_embedding_service_url() -> str:
    embedding_service_url = os.getenv(
        "EMBEDDING_SERVICE_URL",
        DEFAULT_EMBEDDING_SERVICE_URL,
    ).strip()
    if not embedding_service_url:
        return DEFAULT_EMBEDDING_SERVICE_URL
    return embedding_service_url.rstrip("/")


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


def resolve_qdrant_url() -> str:
    qdrant_url = os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL).strip()
    if not qdrant_url:
        return DEFAULT_QDRANT_URL
    return qdrant_url.rstrip("/")


def resolve_qdrant_collection_name() -> str:
    collection_name = os.getenv(
        "QDRANT_COLLECTION_NAME",
        DEFAULT_QDRANT_COLLECTION,
    ).strip()
    if not collection_name:
        return DEFAULT_QDRANT_COLLECTION
    return collection_name


def resolve_qdrant_api_key() -> str | None:
    api_key = os.getenv("QDRANT_API_KEY", "").strip()
    if not api_key:
        return None
    return api_key
