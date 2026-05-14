from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
import unicodedata

from sqlalchemy import text
from sqlalchemy.orm import Session

SOURCE_URL_SQL = "COALESCE(NULLIF(article.canonical_url, ''), 'article://' || article.article_key)"
SOURCE_TITLE_SQL = "COALESCE(NULLIF(article.title, ''), article.article_key)"
SOURCE_AUTHORS_SQL = """
COALESCE(
    (
        SELECT json_agg(
            json_build_object(
                'id', author.id,
                'name', author.display_name
            )
            ORDER BY article_author.position
        )
        FROM article_authors AS article_author
        JOIN authors AS author
            ON author.id = article_author.author_id
        WHERE article_author.article_id = article.article_id
    ),
    '[]'::json
)
"""


def build_source_filters(
    *,
    feed_id: int | None,
    company_id: int | None,
    author_id: int | None,
) -> tuple[list[str], dict[str, object]]:
    filters: list[str] = []
    params: dict[str, object] = {}
    if feed_id is not None:
        filters.append(
            """
            EXISTS (
                SELECT 1
                FROM article_feed_links AS link
                WHERE link.article_id = article.article_id
                    AND link.feed_id = :feed_id
            )
            """
        )
        params["feed_id"] = feed_id
    if company_id is not None:
        filters.append(
            """
            EXISTS (
                SELECT 1
                FROM article_feed_links AS link
                JOIN rss_feeds AS feed
                    ON feed.id = link.feed_id
                WHERE link.article_id = article.article_id
                    AND feed.company_id = :company_id
            )
            """
        )
        params["company_id"] = company_id
    if author_id is not None:
        filters.append(
            """
            EXISTS (
                SELECT 1
                FROM article_authors AS article_author
                WHERE article_author.article_id = article.article_id
                    AND article_author.author_id = :author_id
            )
            """
        )
        params["author_id"] = author_id
    return filters, params


def build_source_search_filters(
    *,
    country: str | None,
    company_id: int | None,
    author_id: int | None,
    published_from: datetime | None,
) -> tuple[list[str], dict[str, object]]:
    filters: list[str] = []
    params: dict[str, object] = {}
    if country:
        filters.append("article.country = :country")
        params["country"] = country
    if company_id is not None:
        filters.append(
            """
            (
                article.company_id = :company_id
                OR EXISTS (
                    SELECT 1
                    FROM article_feed_links AS link
                    JOIN rss_feeds AS feed
                        ON feed.id = link.feed_id
                    WHERE link.article_id = article.article_id
                        AND feed.company_id = :company_id
                )
            )
            """
        )
        params["company_id"] = company_id
    if author_id is not None:
        filters.append(
            """
            EXISTS (
                SELECT 1
                FROM article_authors AS article_author
                WHERE article_author.article_id = article.article_id
                    AND article_author.author_id = :author_id
            )
            """
        )
        params["author_id"] = author_id
    if published_from is not None:
        filters.append("article.published_at >= :published_from")
        params["published_from"] = published_from
    return filters, params


def normalize_lookup_value(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip())
    normalized = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(normalized.lower().split())


def source_extra_values(extra_rows: Sequence[object]) -> tuple[list[str], list[str]]:
    company_names = sorted(
        {
            str(dict(extra_row)["company_name"])
            for extra_row in extra_rows
            if dict(extra_row)["company_name"] is not None
        }
    )
    feed_sections = sorted(
        {
            str(dict(extra_row)["feed_section"])
            for extra_row in extra_rows
            if dict(extra_row)["feed_section"] is not None
        }
    )
    return company_names, feed_sections


def list_company_names_by_source_ids(
    db: Session,
    *,
    source_ids: Sequence[int],
) -> dict[int, list[str]]:
    unique_source_ids = sorted({int(source_id) for source_id in source_ids if int(source_id) > 0})
    if not unique_source_ids:
        return {}
    rows = (
        db.execute(
            text(
                """
                SELECT
                    link.article_id AS source_id,
                    company.name
                FROM article_feed_links AS link
                JOIN rss_feeds AS feed
                    ON feed.id = link.feed_id
                JOIN rss_company AS company
                    ON company.id = feed.company_id
                WHERE link.article_id = ANY(:source_ids)
                    AND company.name IS NOT NULL
                ORDER BY link.article_id ASC, company.name ASC
                """
            ),
            {"source_ids": unique_source_ids},
        )
        .mappings()
        .all()
    )
    company_names_by_source_id: dict[int, list[str]] = {source_id: [] for source_id in unique_source_ids}
    for row in rows:
        source_id = int(row["source_id"])
        company_name = str(row["name"])
        if company_name not in company_names_by_source_id[source_id]:
            company_names_by_source_id[source_id].append(company_name)
    return company_names_by_source_id


def list_source_extra_values_by_source_ids(
    db: Session,
    *,
    source_ids: Sequence[int],
) -> dict[int, tuple[list[str], list[str]]]:
    unique_source_ids = sorted({int(source_id) for source_id in source_ids if int(source_id) > 0})
    if not unique_source_ids:
        return {}
    rows = (
        db.execute(
            text(
                """
                SELECT
                    link.article_id AS source_id,
                    company.name AS company_name,
                    feed.section AS feed_section
                FROM article_feed_links AS link
                JOIN rss_feeds AS feed
                    ON feed.id = link.feed_id
                LEFT JOIN rss_company AS company
                    ON company.id = feed.company_id
                WHERE link.article_id = ANY(:source_ids)
                ORDER BY link.article_id ASC, company.name ASC NULLS LAST, feed.section ASC NULLS LAST
                """
            ),
            {"source_ids": unique_source_ids},
        )
        .mappings()
        .all()
    )
    rows_by_source_id: dict[int, list[object]] = {source_id: [] for source_id in unique_source_ids}
    for row in rows:
        rows_by_source_id[int(row["source_id"])].append(row)
    return {
        source_id: source_extra_values(source_rows)
        for source_id, source_rows in rows_by_source_id.items()
    }
