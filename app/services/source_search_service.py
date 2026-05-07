from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import math

from sqlalchemy.orm import Session

from app.clients.database.source_read_database_client import (
    list_user_source_filtered_search_candidates,
    list_user_source_search_items_by_ids,
    resolve_source_author_id_by_name,
    resolve_source_publisher_id_by_name,
)
from app.clients.embedding.source_search_embedder_client import (
    SourceSearchEmbeddingError,
    get_source_search_query_embedder,
)
from app.clients.qdrant.content_qdrant_client import ContentQdrantClient, QdrantIndexingError
from app.domain.source_embedding_config import (
    resolve_source_search_dimensions,
    resolve_source_search_recency_halflife_days,
)
from app.domain.source_search_query import ParsedNaturalFilter, parse_source_search_query

from shared_backend.errors.app_error import UpstreamServiceError
from shared_backend.schemas.sources.source_schema import (
    AppliedSearchFilterRead,
    SourceSearchMatchedBy,
    UserSourceSearchItemRead,
    UserSourceSearchPageRead,
)
from shared_backend.utils.datetime_utils import normalize_datetime_to_utc


FRESHNESS_WEIGHT = 0.70
RELEVANCE_WEIGHT = 0.30
DENSE_RELEVANCE_WEIGHT = 0.60
SPARSE_RELEVANCE_WEIGHT = 0.40


@dataclass(frozen=True)
class ResolvedSourceSearchFilters:
    language: str | None = None
    publisher_id: int | None = None
    author_id: int | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    applied_filters: list[AppliedSearchFilterRead] = field(default_factory=list)
    unresolved_subject_parts: list[str] = field(default_factory=list)


@dataclass
class SourceSearchAggregate:
    article_id: int
    score: float = 0.0
    published_at: datetime | None = None
    matched_by: set[SourceSearchMatchedBy] = field(default_factory=set)


def search_user_sources(
    db: Session,
    *,
    q: str | None,
    limit: int,
    offset: int,
    language: str | None,
    publisher_id: int | None,
    author_id: int | None,
    published_from: str | None,
    published_to: str | None,
) -> UserSourceSearchPageRead:
    parsed_query = parse_source_search_query(q)
    filters = _resolve_filters(
        db,
        parsed_language=parsed_query.language,
        parsed_publisher_name=parsed_query.publisher_name,
        parsed_author_name=parsed_query.author_name,
        parsed_published_from=parsed_query.published_from,
        parsed_published_to=parsed_query.published_to,
        explicit_language=language,
        explicit_publisher_id=publisher_id,
        explicit_author_id=author_id,
        explicit_published_from=published_from,
        explicit_published_to=published_to,
    )
    subject_query = _join_subject_parts(
        [parsed_query.subject_query, *filters.unresolved_subject_parts]
    )

    if not subject_query:
        candidates = list_user_source_filtered_search_candidates(
            db,
            limit=offset + limit + 1,
            language=filters.language,
            publisher_id=filters.publisher_id,
            author_id=filters.author_id,
            published_from=filters.published_from,
            published_to=filters.published_to,
        )
        page_candidates = candidates[offset:offset + limit]
        return _build_search_page(
            db,
            raw_query=parsed_query.raw_query,
            subject_query=subject_query,
            applied_filters=filters.applied_filters,
            candidates=[
                SourceSearchAggregate(
                    article_id=candidate.article_id,
                    published_at=candidate.published_at,
                )
                for candidate in page_candidates
            ],
            limit=limit,
            offset=offset,
            has_more=len(candidates) > offset + limit,
        )

    pool_size = min(300, offset + limit + 100)
    ranked_candidates = _search_and_rank_vector_candidates(
        subject_query=subject_query,
        limit=pool_size,
        language=filters.language,
        publisher_id=filters.publisher_id,
        author_id=filters.author_id,
        published_from=filters.published_from,
        published_to=filters.published_to,
    )
    page_candidates = ranked_candidates[offset:offset + limit]
    return _build_search_page(
        db,
        raw_query=parsed_query.raw_query,
        subject_query=subject_query,
        applied_filters=filters.applied_filters,
        candidates=page_candidates,
        limit=limit,
        offset=offset,
        has_more=len(ranked_candidates) > offset + limit,
    )


def _search_and_rank_vector_candidates(
    *,
    subject_query: str,
    limit: int,
    language: str | None,
    publisher_id: int | None,
    author_id: int | None,
    published_from: datetime | None,
    published_to: datetime | None,
) -> list[SourceSearchAggregate]:
    try:
        embedder = get_source_search_query_embedder()
        embedding = embedder.embed_query(subject_query)
        expected_dimensions = resolve_source_search_dimensions()
        if len(embedding.dense) != expected_dimensions:
            raise SourceSearchEmbeddingError(
                f"Query embedding dimension mismatch: expected {expected_dimensions}, got {len(embedding.dense)}"
            )
        qdrant_client = ContentQdrantClient()
        sparse_items = qdrant_client.search_sparse_article_embeddings(
            sparse_indices=embedding.sparse.indices,
            sparse_values=embedding.sparse.values,
            limit=limit,
            language=language,
            company_id=publisher_id,
            author_id=author_id,
            published_from=published_from,
            published_to=published_to,
        )
        sparse_article_ids = [item.article_id for item in sparse_items if item.article_id is not None]
        dense_items = qdrant_client.search_dense_article_embeddings(
            dense_vector=embedding.dense,
            limit=limit,
            article_ids=sparse_article_ids or None,
            language=language,
            company_id=publisher_id,
            author_id=author_id,
            published_from=published_from,
            published_to=published_to,
        )
    except (SourceSearchEmbeddingError, QdrantIndexingError, RuntimeError) as exception:
        raise UpstreamServiceError("Source search backend is not ready") from exception

    return _rank_vector_candidates(sparse_items=sparse_items, dense_items=dense_items)


def _resolve_filters(
    db: Session,
    *,
    parsed_language: ParsedNaturalFilter | None,
    parsed_publisher_name: ParsedNaturalFilter | None,
    parsed_author_name: ParsedNaturalFilter | None,
    parsed_published_from: ParsedNaturalFilter | None,
    parsed_published_to: ParsedNaturalFilter | None,
    explicit_language: str | None,
    explicit_publisher_id: int | None,
    explicit_author_id: int | None,
    explicit_published_from: str | None,
    explicit_published_to: str | None,
) -> ResolvedSourceSearchFilters:
    applied_filters: list[AppliedSearchFilterRead] = []
    unresolved_subject_parts: list[str] = []

    language = _normalize_language(explicit_language) or _string_filter_value(parsed_language)
    if language:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="language",
                value=language,
                label=f"Language: {language.upper()}",
                source="explicit" if explicit_language else "inferred",
            )
        )

    resolved_publisher_id = explicit_publisher_id
    if resolved_publisher_id is None and parsed_publisher_name is not None:
        resolved_publisher_id = resolve_source_publisher_id_by_name(
            db,
            publisher_name=str(parsed_publisher_name.value),
        )
        if resolved_publisher_id is None:
            unresolved_subject_parts.append(parsed_publisher_name.raw_text)
    if resolved_publisher_id is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="publisher_id",
                value=resolved_publisher_id,
                label=(
                    f"Publisher: {parsed_publisher_name.value}"
                    if explicit_publisher_id is None and parsed_publisher_name is not None
                    else f"Publisher #{resolved_publisher_id}"
                ),
                source="explicit" if explicit_publisher_id is not None else "inferred",
            )
        )

    resolved_author_id = explicit_author_id
    if resolved_author_id is None and parsed_author_name is not None:
        resolved_author_id = resolve_source_author_id_by_name(
            db,
            author_name=str(parsed_author_name.value),
        )
        if resolved_author_id is None:
            unresolved_subject_parts.append(parsed_author_name.raw_text)
    if resolved_author_id is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="author_id",
                value=resolved_author_id,
                label=(
                    f"Author: {parsed_author_name.value}"
                    if explicit_author_id is None and parsed_author_name is not None
                    else f"Author #{resolved_author_id}"
                ),
                source="explicit" if explicit_author_id is not None else "inferred",
            )
        )

    resolved_published_from = _parse_explicit_datetime(explicit_published_from)
    from_source = "explicit"
    if resolved_published_from is None:
        resolved_published_from = _datetime_filter_value(parsed_published_from)
        from_source = "inferred"
    if resolved_published_from is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="published_from",
                value=resolved_published_from.isoformat(),
                label=f"After {resolved_published_from.date().isoformat()}",
                source=from_source,
            )
        )

    resolved_published_to = _parse_explicit_datetime(explicit_published_to)
    to_source = "explicit"
    if resolved_published_to is None:
        resolved_published_to = _datetime_filter_value(parsed_published_to)
        to_source = "inferred"
    if resolved_published_to is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="published_to",
                value=resolved_published_to.isoformat(),
                label=f"Before {resolved_published_to.date().isoformat()}",
                source=to_source,
            )
        )

    return ResolvedSourceSearchFilters(
        language=language,
        publisher_id=resolved_publisher_id,
        author_id=resolved_author_id,
        published_from=resolved_published_from,
        published_to=resolved_published_to,
        applied_filters=applied_filters,
        unresolved_subject_parts=unresolved_subject_parts,
    )


def _rank_vector_candidates(
    *,
    sparse_items: list,
    dense_items: list,
) -> list[SourceSearchAggregate]:
    aggregates: dict[int, SourceSearchAggregate] = {}
    sparse_scores = _normalize_scores({item.article_id: item.score for item in sparse_items if item.article_id is not None})
    dense_scores = _normalize_scores({item.article_id: item.score for item in dense_items if item.article_id is not None})
    published_at_by_id = {
        item.article_id: normalize_datetime_to_utc(item.published_at)
        for item in [*sparse_items, *dense_items]
        if item.article_id is not None
    }
    now = datetime.now(UTC)
    halflife_days = resolve_source_search_recency_halflife_days()
    for article_id in sorted(set(sparse_scores) | set(dense_scores)):
        sparse_score = sparse_scores.get(article_id, 0.0)
        dense_score = dense_scores.get(article_id, 0.0)
        published_at = published_at_by_id.get(article_id)
        relevance_score = DENSE_RELEVANCE_WEIGHT * dense_score + SPARSE_RELEVANCE_WEIGHT * sparse_score
        freshness_score = _freshness_score(published_at, now=now, halflife_days=halflife_days)
        aggregate = SourceSearchAggregate(
            article_id=article_id,
            score=FRESHNESS_WEIGHT * freshness_score + RELEVANCE_WEIGHT * relevance_score,
            published_at=published_at,
        )
        if sparse_score > 0:
            aggregate.matched_by.add("sparse")
        if dense_score > 0:
            aggregate.matched_by.add("dense")
        aggregates[article_id] = aggregate
    return sorted(
        aggregates.values(),
        key=lambda item: (
            item.score,
            _published_at_sort_value(item.published_at),
            item.article_id,
        ),
        reverse=True,
    )


def _normalize_scores(values: dict[int, float]) -> dict[int, float]:
    if not values:
        return {}
    max_value = max(values.values())
    min_value = min(values.values())
    if math.isclose(max_value, min_value):
        return {article_id: 1.0 for article_id in values}
    scale = max_value - min_value
    return {
        article_id: (score - min_value) / scale
        for article_id, score in values.items()
    }


def _freshness_score(
    published_at: datetime | None,
    *,
    now: datetime,
    halflife_days: float,
) -> float:
    if published_at is None:
        return 0.0
    normalized_published_at = normalize_datetime_to_utc(published_at)
    if normalized_published_at is None:
        return 0.0
    age_seconds = max(0.0, (now - normalized_published_at).total_seconds())
    age_days = age_seconds / 86400.0
    return math.exp(-age_days / halflife_days)


def _build_search_page(
    db: Session,
    *,
    raw_query: str,
    subject_query: str,
    applied_filters: list[AppliedSearchFilterRead],
    candidates: list[SourceSearchAggregate],
    limit: int,
    offset: int,
    has_more: bool,
) -> UserSourceSearchPageRead:
    items_by_id = list_user_source_search_items_by_ids(
        db,
        source_ids=[candidate.article_id for candidate in candidates],
    )
    items: list[UserSourceSearchItemRead] = []
    for candidate in candidates:
        item = items_by_id.get(candidate.article_id)
        if item is None:
            continue
        items.append(
            item.model_copy(
                update={
                    "score": round(candidate.score, 8),
                    "matched_by": _ordered_matches(candidate.matched_by),
                }
            )
        )
    return UserSourceSearchPageRead(
        raw_query=raw_query,
        subject_query=subject_query,
        applied_filters=applied_filters,
        items=items,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


def _ordered_matches(values: set[SourceSearchMatchedBy]) -> list[SourceSearchMatchedBy]:
    return [
        value
        for value in ("sparse", "dense")
        if value in values
    ]


def _join_subject_parts(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip()).strip()


def _string_filter_value(value: ParsedNaturalFilter | None) -> str | None:
    if value is None or not isinstance(value.value, str):
        return None
    return _normalize_language(value.value)


def _datetime_filter_value(value: ParsedNaturalFilter | None) -> datetime | None:
    if value is None or not isinstance(value.value, datetime):
        return None
    return normalize_datetime_to_utc(value.value)


def _parse_explicit_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        return normalize_datetime_to_utc(value.strip())
    except ValueError:
        return None


def _normalize_language(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized


def _published_at_sort_value(value: datetime | None) -> datetime:
    if value is None:
        return datetime(1970, 1, 1, tzinfo=UTC)
    normalized = normalize_datetime_to_utc(value)
    if normalized is None:
        return datetime(1970, 1, 1, tzinfo=UTC)
    return normalized
