from __future__ import annotations

from app.clients.qdrant.content_qdrant_client import QdrantIndexingError, ContentQdrantClient

from shared_backend.errors.app_error import UpstreamServiceError


def check_qdrant_ready() -> None:
    try:
        ContentQdrantClient().check_ready()
    except (QdrantIndexingError, RuntimeError) as exception:
        raise UpstreamServiceError("Qdrant is not ready") from exception
