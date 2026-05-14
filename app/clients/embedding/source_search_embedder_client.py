from __future__ import annotations

from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field

from app.domain.source_embedding_config import (
    resolve_embedding_service_api_key,
    resolve_embedding_service_url,
)


class SourceSearchEmbeddingError(RuntimeError):
    """Raised when bge-m3_inference cannot serve source search embeddings."""


class SparseEmbeddingRead(BaseModel):
    indices: list[int] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)


class EmbeddingServiceItemRead(BaseModel):
    index: int
    embedding: list[float] | None = None
    sparse_embedding: SparseEmbeddingRead | None = None
    colbert_embedding: list[list[float]] | None = None


class EmbeddingServiceResponseRead(BaseModel):
    data: list[EmbeddingServiceItemRead]


@dataclass(frozen=True)
class SourceSearchQueryEmbedding:
    dense: list[float]
    sparse: SparseEmbeddingRead
    model_name: str


class SourceSearchQueryEmbedder:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self.base_url = resolve_embedding_service_url()
        self.api_key = resolve_embedding_service_api_key()
        self._http_client = http_client

    def embed_query(self, subject_query: str) -> SourceSearchQueryEmbedding:
        response = self._request(
            method="POST",
            path="/v1/embeddings",
            json={
                "model": "bge-m3",
                "input": [subject_query],
                "dense": True,
                "sparse": True,
                "colbert": False,
            },
        )
        if response.status_code >= 400:
            raise SourceSearchEmbeddingError(
                f"bge-m3_inference returned HTTP {response.status_code}: {response.text}"
            )
        payload = EmbeddingServiceResponseRead.model_validate(response.json())
        if len(payload.data) != 1:
            raise SourceSearchEmbeddingError("bge-m3_inference returned an unexpected item count")
        item = payload.data[0]
        if not item.embedding:
            raise SourceSearchEmbeddingError("bge-m3_inference returned an empty dense vector")
        if item.sparse_embedding is None:
            raise SourceSearchEmbeddingError("bge-m3_inference returned no sparse vector")
        return SourceSearchQueryEmbedding(
            dense=item.embedding,
            sparse=item.sparse_embedding,
            model_name="bge-m3",
        )

    def check_ready(self) -> None:
        response = self._request(method="GET", path="/internal/ready")
        if response.status_code >= 400:
            raise SourceSearchEmbeddingError(
                f"bge-m3_inference readiness returned HTTP {response.status_code}: {response.text}"
            )

    def _request(
        self,
        *,
        method: str,
        path: str,
        json: dict | None = None,
    ) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=json,
                headers=self._headers(),
            )
        with httpx.Client(timeout=30.0) as client:
            return client.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=json,
                headers=self._headers(),
            )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}


def get_source_search_query_embedder() -> SourceSearchQueryEmbedder:
    return SourceSearchQueryEmbedder()


def reset_source_search_query_embedder() -> None:
    return None
