from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import math

from app.domain.source_embedding_config import resolve_source_search_recency_halflife_days
from app.domain.source_search_query import is_precision_first_query

from shared_backend.schemas.sources.source_schema import SourceSearchMatchedBy
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


@dataclass
class SourceSearchAggregate:
    article_id: int
    score: float = 0.0
    published_at: datetime | None = None
    matched_by: set[SourceSearchMatchedBy] = field(default_factory=set)


def rank_vector_candidates(
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

        published_at = published_at_by_id.get(article_id)
        aggregate = SourceSearchAggregate(
            article_id=article_id,
            score=RELEVANCE_WEIGHT * relevance_score + FRESHNESS_WEIGHT * _freshness_score(
                published_at,
                now=now,
                halflife_days=halflife_days,
            ),
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
            published_at_sort_value(item.published_at),
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


def published_at_sort_value(value: datetime | None) -> datetime:
    if value is None:
        return datetime(1970, 1, 1, tzinfo=UTC)
    normalized = normalize_datetime_to_utc(value)
    if normalized is None:
        return datetime(1970, 1, 1, tzinfo=UTC)
    return normalized
