from __future__ import annotations

from app.clients.embedding.source_search_embedder_client import (
    SourceSearchEmbeddingError,
    get_source_search_query_embedder,
)
from app.clients.qdrant.content_qdrant_client import QdrantIndexingError, ContentQdrantClient

from shared_backend.errors.app_error import UpstreamServiceError


def check_qdrant_ready() -> None:
    try:
        ContentQdrantClient().check_ready()
    except (QdrantIndexingError, RuntimeError) as exception:
        raise UpstreamServiceError("Qdrant is not ready") from exception


def check_source_search_embedder_ready() -> None:
    try:
        get_source_search_query_embedder().check_ready()
    except (SourceSearchEmbeddingError, RuntimeError) as exception:
        raise UpstreamServiceError("Embedding service is not ready") from exception
