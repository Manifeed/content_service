from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.clients.database.source_read_mappers import (
    to_public_published_at,
    to_user_source_search_item_read,
)
from app.clients.database.source_read_support import (
    SOURCE_AUTHORS_SQL,
    SOURCE_TITLE_SQL,
    SOURCE_URL_SQL,
    build_source_search_filters,
    list_source_extra_values_by_source_ids,
)

from shared_backend.schemas.sources.source_schema import UserSourceSearchItemRead


@dataclass(frozen=True)
class SourceSearchCandidateRead:
    article_id: int
    score: float
    published_at: datetime | None


def list_user_source_filtered_search_candidates(
    db: Session,
    *,
    limit: int,
    country: str | None,
    language: str | None,
    themes: list[str] | None,
    company_id: int | None,
    author_id: int | None,
    published_from: datetime | None,
) -> list[SourceSearchCandidateRead]:
    filters, params = build_source_search_filters(
        country=country,
        language=language,
        themes=themes,
        company_id=company_id,
        author_id=author_id,
        published_from=published_from,
    )
    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    article.article_id,
                    article.published_at,
                    0.0 AS score
                FROM articles AS article
                {where_sql}
                ORDER BY article.published_at DESC NULLS LAST, article.article_id DESC
                LIMIT :limit
                """
            ),
            {**params, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [
        SourceSearchCandidateRead(
            article_id=int(dict(row)["article_id"]),
            score=float(dict(row)["score"] or 0.0),
            published_at=to_public_published_at(dict(row)["published_at"]),
        )
        for row in rows
    ]


def list_user_source_search_items_by_ids(
    db: Session,
    *,
    source_ids: Sequence[int],
) -> dict[int, UserSourceSearchItemRead]:
    unique_source_ids = sorted({int(source_id) for source_id in source_ids if int(source_id) > 0})
    if not unique_source_ids:
        return {}
    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    article.article_id AS id,
                    {SOURCE_URL_SQL} AS url,
                    article.published_at,
                    {SOURCE_TITLE_SQL} AS title,
                    article.summary,
                    {SOURCE_AUTHORS_SQL} AS authors
                FROM articles AS article
                WHERE article.article_id = ANY(:source_ids)
                """
            ),
            {"source_ids": unique_source_ids},
        )
        .mappings()
        .all()
    )
    extra_values_by_source_id = list_source_extra_values_by_source_ids(
        db,
        source_ids=unique_source_ids,
    )
    items: dict[int, UserSourceSearchItemRead] = {}
    for row in rows:
        item = to_user_source_search_item_read(
            row,
            extra_values_by_source_id=extra_values_by_source_id,
        )
        items[item.id] = item
    return items
