from __future__ import annotations

from sqlalchemy.orm import Session

from app.clients.database.source_read_database_client import list_user_source_search_items_by_ids
from app.services.source_search_ranking import SourceSearchAggregate

from shared_backend.schemas.sources.source_schema import (
    AppliedSearchFilterRead,
    SourceSearchMatchedBy,
    UserSourceSearchItemRead,
    UserSourceSearchPageRead,
)


def build_source_search_page(
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
                    "matched_by": ordered_source_search_matches(candidate.matched_by),
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


def ordered_source_search_matches(
    values: set[SourceSearchMatchedBy],
) -> list[SourceSearchMatchedBy]:
    return [value for value in ("sparse", "dense") if value in values]
