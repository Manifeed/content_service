from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import math

from sqlalchemy.orm import Session

from app.clients.database.source_read_database_client import (
    list_user_source_filtered_search_candidates,
    list_user_source_search_items_by_ids,
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
from app.domain.source_search_query import (
    is_precision_first_query,
    parse_source_search_query,
)

from shared_backend.errors.app_error import UpstreamServiceError
from shared_backend.schemas.sources.source_schema import (
    AppliedSearchFilterRead,
    SourceSearchMatchedBy,
    UserSourceSearchItemRead,
    UserSourceSearchPageRead,
)
from shared_backend.utils.datetime_utils import normalize_datetime_to_utc


FRESHNESS_WEIGHT = 0.45
RELEVANCE_WEIGHT = 0.55
SPARSE_RELEVANCE_WEIGHT = 0.60
DENSE_RELEVANCE_WEIGHT = 0.40
MIN_RELEVANCE_SCORE = 0.42
MIN_PRECISION_FIRST_RELEVANCE_SCORE = 0.55
MIN_DENSE_RAW_SCORE = 0.22
MIN_SPARSE_RAW_SCORE = 0.01
RECENT_ARTICLE_BOOST_HOURS = 48
SOURCE_SEARCH_PERIODS: dict[str, timedelta | None] = {
    "all": None,
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "1m": timedelta(days=31),
    "1y": timedelta(days=365),
}


@dataclass(frozen=True)
class ResolvedSourceSearchFilters:
    country: str | None = None
    company_id: int | None = None
    author_id: int | None = None
    published_from: datetime | None = None
    published_period: str = "all"
    applied_filters: list[AppliedSearchFilterRead] = field(default_factory=list)


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
    country: str | None,
    company_id: int | None,
    author_id: int | None,
    period: str | None,
) -> UserSourceSearchPageRead:
    parsed_query = parse_source_search_query(q)
    filters = _resolve_filters(
        explicit_country=country,
        explicit_company_id=company_id,
        explicit_author_id=author_id,
        explicit_period=period,
    )
    subject_query = parsed_query.subject_query

    if not subject_query:
        candidates = list_user_source_filtered_search_candidates(
            db,
            limit=offset + limit + 1,
            country=filters.country,
            company_id=filters.company_id,
            author_id=filters.author_id,
            published_from=filters.published_from,
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
        country=filters.country,
        company_id=filters.company_id,
        author_id=filters.author_id,
        published_from=filters.published_from,
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
    country: str | None,
    company_id: int | None,
    author_id: int | None,
    published_from: datetime | None,
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
            country=country,
            company_id=company_id,
            author_id=author_id,
            published_from=published_from,
        )
        sparse_article_ids = [item.article_id for item in sparse_items if item.article_id is not None]
        dense_items = qdrant_client.search_dense_article_embeddings(
            dense_vector=embedding.dense,
            limit=limit,
            article_ids=sparse_article_ids or None,
            country=country,
            company_id=company_id,
            author_id=author_id,
            published_from=published_from,
        )
    except (SourceSearchEmbeddingError, QdrantIndexingError, RuntimeError) as exception:
        raise UpstreamServiceError("Source search backend is not ready") from exception

    return _rank_vector_candidates(
        subject_query=subject_query,
        sparse_items=sparse_items,
        dense_items=dense_items,
    )


def _resolve_filters(
    *,
    explicit_country: str | None,
    explicit_company_id: int | None,
    explicit_author_id: int | None,
    explicit_period: str | None,
) -> ResolvedSourceSearchFilters:
    applied_filters: list[AppliedSearchFilterRead] = []

    country = _normalize_country(explicit_country)
    if country:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="country",
                value=country,
                label=f"Country: {country.upper()}",
            )
        )

    if explicit_company_id is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="company_id",
                value=explicit_company_id,
                label=f"Company #{explicit_company_id}",
            )
        )

    if explicit_author_id is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="author_id",
                value=explicit_author_id,
                label=f"Author #{explicit_author_id}",
            )
        )

    resolved_period = _normalize_period(explicit_period)
    resolved_published_from = _resolve_period_start(resolved_period)
    if resolved_published_from is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="published_period",
                value=resolved_period,
                label=f"Period: {resolved_period.upper()}",
            )
        )

    return ResolvedSourceSearchFilters(
        country=country,
        company_id=explicit_company_id,
        author_id=explicit_author_id,
        published_from=resolved_published_from,
        published_period=resolved_period,
        applied_filters=applied_filters,
    )


def _rank_vector_candidates(
    *,
    sparse_items: list,
    dense_items: list,
    subject_query: str = "",
) -> list[SourceSearchAggregate]:
    sparse_raw = {item.article_id: item.score for item in sparse_items if item.article_id is not None}
    dense_raw = {item.article_id: item.score for item in dense_items if item.article_id is not None}
    sparse_scores = _normalize_scores(sparse_raw)
    dense_scores = _normalize_scores(dense_raw)
    published_at_by_id = {
        item.article_id: normalize_datetime_to_utc(item.published_at)
        for item in [*sparse_items, *dense_items]
        if item.article_id is not None
    }
    now = datetime.now(UTC)
    halflife_days = resolve_source_search_recency_halflife_days()
    precision_first = is_precision_first_query(subject_query)
    aggregates: dict[int, SourceSearchAggregate] = {}
    for article_id in sorted(set(sparse_scores) | set(dense_scores)):
        sparse_score = sparse_scores.get(article_id, 0.0)
        dense_score = dense_scores.get(article_id, 0.0)
        has_sparse_match = sparse_raw.get(article_id, 0.0) > 0.0
        has_dense_match = dense_raw.get(article_id, 0.0) > 0.0
        published_at = published_at_by_id.get(article_id)
        relevance_score = (
            SPARSE_RELEVANCE_WEIGHT * sparse_score
            + DENSE_RELEVANCE_WEIGHT * dense_score
        )
        if not _is_search_candidate_relevant(
            relevance_score=relevance_score,
            sparse_raw_score=sparse_raw.get(article_id, 0.0),
            dense_raw_score=dense_raw.get(article_id, 0.0),
            has_sparse_match=has_sparse_match,
            has_dense_match=has_dense_match,
            precision_first=precision_first,
        ):
            continue
        freshness_score = _freshness_score(published_at, now=now, halflife_days=halflife_days)
        aggregate = SourceSearchAggregate(
            article_id=article_id,
            score=RELEVANCE_WEIGHT * relevance_score + FRESHNESS_WEIGHT * freshness_score,
            published_at=published_at,
        )
        if has_sparse_match:
            aggregate.matched_by.add("sparse")
        if has_dense_match:
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


def _is_search_candidate_relevant(
    *,
    relevance_score: float,
    sparse_raw_score: float,
    dense_raw_score: float,
    has_sparse_match: bool,
    has_dense_match: bool,
    precision_first: bool,
) -> bool:
    if not (has_sparse_match and has_dense_match):
        return False
    if sparse_raw_score < MIN_SPARSE_RAW_SCORE or dense_raw_score < MIN_DENSE_RAW_SCORE:
        return False
    minimum_score = (
        MIN_PRECISION_FIRST_RELEVANCE_SCORE
        if precision_first
        else MIN_RELEVANCE_SCORE
    )
    return relevance_score >= minimum_score


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
    if age_seconds <= RECENT_ARTICLE_BOOST_HOURS * 3600:
        return 1.0
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


def _normalize_period(value: str | None) -> str:
    normalized = (value or "all").strip().casefold()
    return normalized if normalized in SOURCE_SEARCH_PERIODS else "all"


def _resolve_period_start(period: str) -> datetime | None:
    delta = SOURCE_SEARCH_PERIODS[period]
    if delta is None:
        return None
    return datetime.now(UTC) - delta


def _normalize_country(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()[:2]
    return normalized or None


def _published_at_sort_value(value: datetime | None) -> datetime:
    if value is None:
        return datetime(1970, 1, 1, tzinfo=UTC)
    normalized = normalize_datetime_to_utc(value)
    if normalized is None:
        return datetime(1970, 1, 1, tzinfo=UTC)
    return normalized
