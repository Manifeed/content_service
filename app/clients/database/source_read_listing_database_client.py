from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.clients.database.source_read_mappers import to_user_source_read
from app.clients.database.source_read_support import (
    SOURCE_AUTHORS_SQL,
    SOURCE_TITLE_SQL,
    SOURCE_URL_SQL,
    list_company_names_by_source_ids,
)

from shared_backend.schemas.sources.source_schema import UserSourceRead


def list_user_sources_read(
    db: Session,
    *,
    limit: int,
    offset: int,
) -> tuple[list[UserSourceRead], int]:
    total = count_sources(db)
    if total == 0:
        return [], 0
    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    article.article_id AS id,
                    {SOURCE_URL_SQL} AS url,
                    article.published_at,
                    {SOURCE_TITLE_SQL} AS title,
                    {SOURCE_AUTHORS_SQL} AS authors
                FROM articles AS article
                ORDER BY article.published_at DESC NULLS LAST, article.article_id DESC
                LIMIT :limit
                OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        )
        .mappings()
        .all()
    )
    company_names_by_source_id = list_company_names_by_source_ids(
        db,
        source_ids=[int(row["id"]) for row in rows],
    )
    return [
        to_user_source_read(row, company_names_by_source_id=company_names_by_source_id)
        for row in rows
    ], total


def count_sources(db: Session) -> int:
    return int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM articles AS article
                """
            )
        ).scalar_one()
        or 0
    )
