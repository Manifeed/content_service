from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.clients.database.source_read_mappers import (
    parse_source_authors,
    to_public_image_url,
    to_public_published_at,
    to_public_source_url,
)
from app.clients.database.source_read_support import (
    SOURCE_AUTHORS_SQL,
    SOURCE_TITLE_SQL,
    SOURCE_URL_SQL,
    source_extra_values,
)

from shared_backend.schemas.sources.source_schema import (
    RssSourceDetailRead,
    UserSourceDetailRead,
)


def get_rss_source_detail_read_by_id(db: Session, source_id: int) -> RssSourceDetailRead | None:
    row = (
        db.execute(
            text(
                f"""
                SELECT
                    article.article_id AS id,
                    {SOURCE_URL_SQL} AS url,
                    article.published_at,
                    {SOURCE_TITLE_SQL} AS title,
                    article.summary,
                    {SOURCE_AUTHORS_SQL} AS authors,
                    article.image_url
                FROM articles AS article
                WHERE article.article_id = :source_id
                """
            ),
            {"source_id": source_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    company_names, feed_sections = _load_detail_extra_values(db, source_id=source_id)
    return RssSourceDetailRead(
        id=int(row["id"]),
        title=str(row["title"]),
        summary=(str(row["summary"]) if row["summary"] is not None else None),
        authors=parse_source_authors(row["authors"]),
        url=to_public_source_url(row["url"]),
        published_at=to_public_published_at(row["published_at"]),
        image_url=to_public_image_url(row["image_url"]),
        company_names=company_names,
        feed_sections=feed_sections,
    )


def get_user_source_detail_read_by_id(
    db: Session,
    source_id: int,
) -> UserSourceDetailRead | None:
    row = (
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
                WHERE article.article_id = :source_id
                """
            ),
            {"source_id": source_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    company_names, feed_sections = _load_detail_extra_values(db, source_id=source_id)
    return UserSourceDetailRead(
        id=int(row["id"]),
        title=str(row["title"]),
        summary=(str(row["summary"]) if row["summary"] is not None else None),
        authors=parse_source_authors(row["authors"]),
        url=to_public_source_url(row["url"]),
        published_at=to_public_published_at(row["published_at"]),
        company_names=company_names,
        feed_sections=feed_sections,
    )


def _load_detail_extra_values(
    db: Session,
    *,
    source_id: int,
) -> tuple[list[str], list[str]]:
    extra_rows = (
        db.execute(
            text(
                """
                SELECT
                    company.name AS company_name,
                    feed.section AS feed_section
                FROM article_feed_links AS link
                JOIN rss_feeds AS feed
                    ON feed.id = link.feed_id
                LEFT JOIN rss_company AS company
                    ON company.id = feed.company_id
                WHERE link.article_id = :source_id
                ORDER BY company.name ASC NULLS LAST, feed.section ASC NULLS LAST
                """
            ),
            {"source_id": source_id},
        )
        .mappings()
        .all()
    )
    return source_extra_values(extra_rows)
