from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
import httpx

from app.domain.source_embedding_config import (
    resolve_qdrant_api_key,
    resolve_qdrant_collection_name,
    resolve_qdrant_url,
)

_ENSURED_COLLECTIONS: dict[str, int] = {}


class QdrantIndexingError(RuntimeError):
    """Raised when a Qdrant operation fails."""


@dataclass(frozen=True)
class QdrantArticleEmbeddingPointRead:
    point_id: str
    article_id: int | None
    article_key: str
    model_name: str
    company_id: int | None
    company: str | None
    language: str | None
    published_at: str | None
    url: str | None
    title: str | None
    summary: str | None
    feed_ids: list[int]
    feeds: list[dict]
    author_ids: list[int]
    authors: list[str]
    images_url: list[str]
    vector: list[float]


@dataclass(frozen=True)
class QdrantArticleEmbeddingPointSummaryRead:
    point_id: str
    article_id: int | None
    article_key: str | None
    model_name: str | None


@dataclass(frozen=True)
class QdrantScoredArticleEmbeddingPointRead:
    point_id: str
    score: float
    article_id: int | None
    article_key: str | None
    model_name: str | None
    published_at: datetime | None = None


class ContentQdrantClient:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self.base_url = resolve_qdrant_url()
        self.collection_name = resolve_qdrant_collection_name()
        self.api_key = resolve_qdrant_api_key()
        self._http_client = http_client

    def upsert_article_embedding(
        self,
        *,
        article_id: int,
        article_key: str,
        worker_version: str,
        vector: list[float],
        url: str,
        title: str,
        summary: str | None,
        company_id: int | None,
        company: str | None,
        language: str | None,
        published_at: datetime | None,
        feed_ids: list[int],
        feeds: list[dict],
        author_ids: list[int],
        authors: list[str],
        images_url: list[str],
    ) -> str:
        dimensions = len(vector)
        self._ensure_collection(dimensions=dimensions)
        point_id = build_article_embedding_point_id(
            article_key=article_key,
            worker_version=worker_version,
        )
        payload = {
            "article_id": article_id,
            "article_key": article_key,
            "model_name": worker_version,
            "url": url,
            "title": title,
            "summary": summary,
            "company_id": company_id,
            "company": company,
            "language": language,
            "published_at": (
                published_at.isoformat()
                if published_at is not None
                else None
            ),
            "feed_ids": feed_ids,
            "feeds": feeds,
            "author_ids": author_ids,
            "authors": authors,
            "images_url": images_url,
        }
        response = self._request(
            method="PUT",
            path=f"/collections/{self.collection_name}/points?wait=true",
            json={
                "points": [
                    {
                        "id": point_id,
                        "vector": vector,
                        "payload": payload,
                    }
                ],
            },
        )
        self._require_qdrant_success(response, "Unable to upsert embedding point")
        return point_id

    def get_article_embedding_point(
        self,
        *,
        article_key: str,
        worker_version: str,
    ) -> QdrantArticleEmbeddingPointRead | None:
        point_id = build_article_embedding_point_id(
            article_key=article_key,
            worker_version=worker_version,
        )
        response = self._request(
            method="POST",
            path=f"/collections/{self.collection_name}/points",
            json={
                "ids": [point_id],
                "with_payload": True,
                "with_vector": True,
            },
        )
        self._require_qdrant_success(response, "Unable to read embedding point")
        points = response.json().get("result") or []
        if not points:
            return None

        point = points[0]
        payload = point.get("payload") or {}
        raw_vector = point.get("vector")
        if not isinstance(raw_vector, list):
            raise QdrantIndexingError(
                f"Unable to read embedding point {point_id}: vector missing from payload"
            )
        vector = [float(value) for value in raw_vector]
        return QdrantArticleEmbeddingPointRead(
            point_id=str(point.get("id") or point_id),
            article_id=(
                int(payload["article_id"])
                if payload.get("article_id") is not None
                else None
            ),
            article_key=str(payload.get("article_key") or article_key),
            model_name=str(payload.get("model_name") or payload.get("worker_version") or worker_version),
            company_id=(
                int(payload["company_id"])
                if payload.get("company_id") is not None
                else None
            ),
            language=(
                str(payload["language"])
                if payload.get("language") is not None
                else None
            ),
            published_at=(
                str(payload["published_at"])
                if payload.get("published_at") is not None
                else None
            ),
            company=(str(payload["company"]) if payload.get("company") is not None else None),
            url=(str(payload["url"]) if payload.get("url") is not None else None),
            title=(str(payload["title"]) if payload.get("title") is not None else None),
            summary=(str(payload["summary"]) if payload.get("summary") is not None else None),
            feed_ids=[
                int(feed_id)
                for feed_id in (payload.get("feed_ids") or [])
                if isinstance(feed_id, int)
            ],
            feeds=[
                dict(feed)
                for feed in (payload.get("feeds") or [])
                if isinstance(feed, dict)
            ],
            author_ids=[
                int(author_id)
                for author_id in (payload.get("author_ids") or [])
                if isinstance(author_id, int)
            ],
            authors=[
                str(author)
                for author in (payload.get("authors") or [])
                if isinstance(author, str)
            ],
            images_url=[
                str(image_url)
                for image_url in (payload.get("images_url") or [])
                if isinstance(image_url, str)
            ],
            vector=vector,
        )

    def delete_point_ids(self, point_ids: list[str]) -> None:
        unique_point_ids = sorted({point_id for point_id in point_ids if point_id})
        if not unique_point_ids:
            return
        response = self._request(
            method="POST",
            path=f"/collections/{self.collection_name}/points/delete?wait=true",
            json={
                "points": unique_point_ids,
            },
        )
        self._require_qdrant_success(response, "Unable to delete embedding points")

    def scroll_article_embedding_points(
        self,
        *,
        limit: int,
        offset: str | None = None,
    ) -> tuple[list[QdrantArticleEmbeddingPointSummaryRead], str | None]:
        payload: dict[str, object] = {
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            payload["offset"] = offset
        response = self._request(
            method="POST",
            path=f"/collections/{self.collection_name}/points/scroll",
            json=payload,
        )
        self._require_qdrant_success(response, "Unable to scroll embedding points")
        result = response.json().get("result") or {}
        points = result.get("points") or []
        items = [
            QdrantArticleEmbeddingPointSummaryRead(
                point_id=str(point.get("id")),
                article_id=(
                    int(payload["article_id"])
                    if isinstance((payload := point.get("payload") or {}).get("article_id"), int)
                    else None
                ),
                article_key=(
                    str(payload["article_key"])
                    if payload.get("article_key") is not None
                    else None
                ),
                model_name=(
                    str(payload["model_name"])
                    if payload.get("model_name") is not None
                    else None
                ),
            )
            for point in points
        ]
        next_offset = result.get("next_page_offset")
        return items, (str(next_offset) if next_offset is not None else None)

    def search_similar_article_embeddings(
        self,
        *,
        article_id: int,
        limit: int,
    ) -> list[QdrantScoredArticleEmbeddingPointRead]:
        response = self._request(
            method="POST",
            path=f"/collections/{self.collection_name}/points/recommend",
            json={
                "positive": [article_id],
                "using": "dense",
                "limit": max(1, int(limit)),
                "with_payload": True,
                "with_vector": False,
            },
        )
        self._require_qdrant_success(response, "Unable to search similar embedding points")
        points = response.json().get("result") or []
        return [
            QdrantScoredArticleEmbeddingPointRead(
                point_id=str(point.get("id")),
                score=float(point.get("score") or 0.0),
                article_id=(
                    int(payload["article_id"])
                    if isinstance((payload := point.get("payload") or {}).get("article_id"), int)
                    else None
                ),
                article_key=(
                    str(payload["article_key"])
                    if payload.get("article_key") is not None
                    else None
                ),
                model_name=(
                    str(payload["model_name"])
                    if payload.get("model_name") is not None
                    else None
                ),
                published_at=_parse_qdrant_datetime(payload.get("published_at")),
            )
            for point in points
        ]

    def search_sparse_article_embeddings(
        self,
        *,
        sparse_indices: list[int],
        sparse_values: list[float],
        limit: int,
        language: str | None = None,
        company_id: int | None = None,
        author_id: int | None = None,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
    ) -> list[QdrantScoredArticleEmbeddingPointRead]:
        return self._search_named_article_embeddings(
            vector_name="sparse",
            vector={
                "indices": sparse_indices,
                "values": sparse_values,
            },
            limit=limit,
            language=language,
            company_id=company_id,
            author_id=author_id,
            published_from=published_from,
            published_to=published_to,
        )

    def search_dense_article_embeddings(
        self,
        *,
        dense_vector: list[float],
        limit: int,
        article_ids: list[int] | None = None,
        language: str | None = None,
        company_id: int | None = None,
        author_id: int | None = None,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
    ) -> list[QdrantScoredArticleEmbeddingPointRead]:
        return self._search_named_article_embeddings(
            vector_name="dense",
            vector=dense_vector,
            limit=limit,
            article_ids=article_ids,
            language=language,
            company_id=company_id,
            author_id=author_id,
            published_from=published_from,
            published_to=published_to,
        )

    def _search_named_article_embeddings(
        self,
        *,
        vector_name: str,
        vector: dict[str, list[int] | list[float]] | list[float],
        limit: int,
        article_ids: list[int] | None = None,
        language: str | None = None,
        company_id: int | None = None,
        author_id: int | None = None,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
    ) -> list[QdrantScoredArticleEmbeddingPointRead]:
        payload: dict[str, object] = {
            "vector": {
                "name": vector_name,
                "vector": vector,
            },
            "limit": max(1, int(limit)),
            "with_payload": True,
            "with_vector": False,
        }
        filter_payload = build_qdrant_source_search_filter(
            article_ids=article_ids,
            language=language,
            company_id=company_id,
            author_id=author_id,
            published_from=published_from,
            published_to=published_to,
        )
        if filter_payload is not None:
            payload["filter"] = filter_payload

        response = self._request(
            method="POST",
            path=f"/collections/{self.collection_name}/points/search",
            json=payload,
        )
        self._require_qdrant_success(response, "Unable to search embedding points")
        points = response.json().get("result") or []
        return [
            QdrantScoredArticleEmbeddingPointRead(
                point_id=str(point.get("id")),
                score=float(point.get("score") or 0.0),
                article_id=(
                    int(payload["article_id"])
                    if isinstance((payload := point.get("payload") or {}).get("article_id"), int)
                    else None
                ),
                article_key=(
                    str(payload["article_key"])
                    if payload.get("article_key") is not None
                    else None
                ),
                model_name=(
                    str(payload["model_name"])
                    if payload.get("model_name") is not None
                    else None
                ),
                published_at=_parse_qdrant_datetime(payload.get("published_at")),
            )
            for point in points
        ]

    def check_ready(self) -> None:
        response = self._request(method="GET", path="/collections")
        self._require_qdrant_success(response, "Unable to read Qdrant collections")

    def _ensure_collection(
        self,
        *,
        dimensions: int,
    ) -> None:
        cached_dimensions = _ENSURED_COLLECTIONS.get(self.collection_name)
        if cached_dimensions == dimensions:
            return

        response = self._request(
            method="GET",
            path=f"/collections/{self.collection_name}",
        )
        if response.status_code == 404:
            create_response = self._request(
                method="PUT",
                path=f"/collections/{self.collection_name}",
                json={
                    "vectors": {
                        "dense": {
                            "size": dimensions,
                            "distance": "Cosine",
                        },
                    },
                    "sparse_vectors": {
                        "sparse": {},
                    },
                },
            )
            self._require_qdrant_success(
                create_response,
                "Unable to create Qdrant collection",
            )
            self._ensure_payload_indexes()
            _ENSURED_COLLECTIONS[self.collection_name] = dimensions
            return

        self._require_qdrant_success(response, "Unable to read Qdrant collection")
        payload = response.json().get("result", {})
        config = payload.get("config", {})
        params = config.get("params", {})
        vectors = params.get("vectors", {})
        dense_config = vectors.get("dense") if isinstance(vectors, dict) else {}
        remote_dimensions = int((dense_config or {}).get("size") or vectors.get("size") or 0)
        if remote_dimensions != dimensions:
            raise QdrantIndexingError(
                "Qdrant collection dimension mismatch: "
                f"expected {dimensions}, found {remote_dimensions}"
            )
        self._ensure_payload_indexes()
        _ENSURED_COLLECTIONS[self.collection_name] = dimensions

    def rebuild_collection(self, *, dimensions: int) -> None:
        delete_response = self._request(
            method="DELETE",
            path=f"/collections/{self.collection_name}",
        )
        if delete_response.status_code != 404:
            self._require_qdrant_success(delete_response, "Unable to delete Qdrant collection")
        _ENSURED_COLLECTIONS.pop(self.collection_name, None)
        create_response = self._request(
            method="PUT",
            path=f"/collections/{self.collection_name}",
            json={
                "vectors": {
                    "dense": {
                        "size": dimensions,
                        "distance": "Cosine",
                    },
                },
                "sparse_vectors": {
                    "sparse": {},
                },
            },
        )
        self._require_qdrant_success(create_response, "Unable to recreate Qdrant collection")
        self._ensure_payload_indexes()
        _ENSURED_COLLECTIONS[self.collection_name] = dimensions

    def _ensure_payload_indexes(self) -> None:
        for field_name, field_schema in (
            ("language", "keyword"),
            ("published_at", "datetime"),
            ("feed_ids", "integer"),
            ("company_id", "integer"),
            ("author_ids", "integer"),
        ):
            response = self._request(
                method="PUT",
                path=f"/collections/{self.collection_name}/index",
                json={
                    "field_name": field_name,
                    "field_schema": field_schema,
                },
            )
            self._require_qdrant_success(
                response,
                f"Unable to create Qdrant payload index for {field_name}",
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
                headers=self._build_headers(),
            )
        with httpx.Client(timeout=20.0) as client:
            return client.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=json,
                headers=self._build_headers(),
            )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key is not None:
            headers["api-key"] = self.api_key
        return headers

    def _require_qdrant_success(
        self,
        response: httpx.Response,
        message: str,
    ) -> None:
        if response.status_code >= 400:
            raise QdrantIndexingError(
                f"{message}: HTTP {response.status_code} - {response.text}"
            )
        payload = response.json()
        if payload.get("status") not in (None, "ok"):
            raise QdrantIndexingError(
                f"{message}: unexpected Qdrant payload {payload}"
            )


def build_article_embedding_point_id(
    *,
    article_key: str,
    worker_version: str,
) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"{article_key}:{worker_version}",
        )
    )


def build_qdrant_source_search_filter(
    *,
    article_ids: list[int] | None = None,
    language: str | None,
    company_id: int | None,
    author_id: int | None,
    published_from: datetime | None,
    published_to: datetime | None,
) -> dict[str, list[dict[str, object]]] | None:
    must_conditions: list[dict[str, object]] = []
    if article_ids:
        must_conditions.append({"has_id": sorted({int(article_id) for article_id in article_ids})})
    if language:
        must_conditions.append({"key": "language", "match": {"value": language}})
    if company_id is not None:
        must_conditions.append({"key": "company_id", "match": {"value": company_id}})
    if author_id is not None:
        must_conditions.append({"key": "author_ids", "match": {"value": author_id}})
    range_filter: dict[str, str] = {}
    if published_from is not None:
        range_filter["gte"] = published_from.isoformat()
    if published_to is not None:
        range_filter["lte"] = published_to.isoformat()
    if range_filter:
        must_conditions.append({"key": "published_at", "range": range_filter})
    if not must_conditions:
        return None
    return {"must": must_conditions}


def _parse_qdrant_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed
