from __future__ import annotations

from shared_backend.clients.qdrant_client import QdrantIndexingError
from shared_backend.errors.app_error import UpstreamServiceError

from app.clients.qdrant.content_qdrant_client import ContentQdrantClient


def check_qdrant_ready() -> None:
    try:
        ContentQdrantClient().check_ready()
    except (QdrantIndexingError, RuntimeError) as exception:
        raise UpstreamServiceError("Qdrant is not ready") from exception
