from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import unicodedata

from sqlalchemy import text
from sqlalchemy.orm import Session

from shared_backend.schemas.sources.source_schema import (
    RssSourceAuthorRead,
    RssSourceDetailRead,
    RssSourceRead,
    UserSourceDetailRead,
    UserSourceRead,
    UserSourceSearchItemRead,
)
from shared_backend.utils.datetime_utils import normalize_datetime_to_utc
from shared_backend.utils.public_url import normalize_public_http_url


SOURCE_PUBLISHED_AT_FALLBACK = datetime(1970, 1, 1, tzinfo=timezone.utc)
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


@dataclass(frozen=True)
class SourceSearchCandidateRead:
    article_id: int
    score: float
    published_at: datetime | None


def list_rss_sources_read(
    db: Session,
    *,
    limit: int,
    offset: int,
    feed_id: int | None = None,
    company_id: int | None = None,
    author_id: int | None = None,
) -> tuple[list[RssSourceRead], int]:
    filters, params = _build_source_filters(feed_id=feed_id, company_id=company_id, author_id=author_id)
    where_sql = ''
    if filters:
        where_sql = 'WHERE ' + ' AND '.join(filters)
    total = int(
        db.execute(
            text(  # nosec
                f"""
                SELECT COUNT(*)
                FROM articles AS article
                {where_sql}
                """
            ),
            params,
        ).scalar_one()
        or 0
    )
    if total == 0:
        return [], 0
    rows = (
        db.execute(
            text(  # nosec
                f"""
                SELECT
                    article.article_id AS id,
                    {SOURCE_URL_SQL} AS url,
                    article.published_at,
                    {SOURCE_TITLE_SQL} AS title,
                    {SOURCE_AUTHORS_SQL} AS authors,
                    article.image_url
                FROM articles AS article
                {where_sql}
                ORDER BY article.published_at DESC NULLS LAST, article.article_id DESC
                LIMIT :limit
                OFFSET :offset
                """
            ),
            {**params, 'limit': limit, 'offset': offset},
        )
        .mappings()
        .all()
    )
    company_names_by_source_id = _list_company_names_by_source_ids(
        db,
        source_ids=[int(row['id']) for row in rows],
    )
    return [
        _to_rss_source_read(row, company_names_by_source_id=company_names_by_source_id)
        for row in rows
    ], total


def list_user_sources_read(
    db: Session,
    *,
    limit: int,
    offset: int,
) -> tuple[list[UserSourceRead], int]:
    total = int(
        db.execute(
            text(  # nosec
                """
                SELECT COUNT(*)
                FROM articles AS article
                """
            )
        ).scalar_one()
        or 0
    )
    if total == 0:
        return [], 0

    rows = (
        db.execute(
            text(  # nosec
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
    company_names_by_source_id = _list_company_names_by_source_ids(
        db,
        source_ids=[int(row["id"]) for row in rows],
    )
    return [
        _to_user_source_read(row, company_names_by_source_id=company_names_by_source_id)
        for row in rows
    ], total


def list_user_source_lexical_search_candidates(
    db: Session,
    *,
    query: str,
    limit: int,
    language: str | None,
    publisher_id: int | None,
    author_id: int | None,
    published_from: datetime | None,
    published_to: datetime | None,
) -> list[SourceSearchCandidateRead]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    filters, params = _build_source_search_filters(
        language=language,
        publisher_id=publisher_id,
        author_id=author_id,
        published_from=published_from,
        published_to=published_to,
    )
    filters.append(
        """
        to_tsvector('simple', COALESCE(article.title, '') || ' ' || COALESCE(article.summary, ''))
            @@ plainto_tsquery('simple', :query)
        """
    )
    params["query"] = normalized_query
    where_sql = "WHERE " + " AND ".join(filters)
    rows = (
        db.execute(
            text(  # nosec
                f"""
                SELECT
                    article.article_id,
                    article.published_at,
                    ts_rank_cd(
                        to_tsvector('simple', COALESCE(article.title, '') || ' ' || COALESCE(article.summary, '')),
                        plainto_tsquery('simple', :query)
                    ) AS score
                FROM articles AS article
                {where_sql}
                ORDER BY score DESC, article.published_at DESC NULLS LAST, article.article_id DESC
                LIMIT :limit
                """
            ),
            {**params, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [_to_source_search_candidate(row) for row in rows]


def list_user_source_filtered_search_candidates(
    db: Session,
    *,
    limit: int,
    language: str | None,
    publisher_id: int | None,
    author_id: int | None,
    published_from: datetime | None,
    published_to: datetime | None,
) -> list[SourceSearchCandidateRead]:
    filters, params = _build_source_search_filters(
        language=language,
        publisher_id=publisher_id,
        author_id=author_id,
        published_from=published_from,
        published_to=published_to,
    )
    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)
    rows = (
        db.execute(
            text(  # nosec
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
    return [_to_source_search_candidate(row) for row in rows]


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
    extra_values_by_source_id = _list_source_extra_values_by_source_ids(
        db,
        source_ids=unique_source_ids,
    )
    items: dict[int, UserSourceSearchItemRead] = {}
    for row in rows:
        item = _to_user_source_search_item_read(
            row,
            extra_values_by_source_id=extra_values_by_source_id,
        )
        items[item.id] = item
    return items


def count_sources(db: Session) -> int:
    return int(
        db.execute(
            text(  # nosec
                """
                SELECT COUNT(*)
                FROM articles AS article
                """
            )
        ).scalar_one()
        or 0
    )


def resolve_source_publisher_id_by_name(db: Session, *, publisher_name: str) -> int | None:
    normalized_name = _normalize_lookup_value(publisher_name)
    if not normalized_name:
        return None
    row = (
        db.execute(
            text(
                """
                SELECT company.id
                FROM rss_company AS company
                WHERE lower(company.name) = lower(:publisher_name)
                    OR company.name ILIKE :publisher_like
                ORDER BY
                    CASE WHEN lower(company.name) = lower(:publisher_name) THEN 0 ELSE 1 END,
                    length(company.name) ASC,
                    company.id ASC
                LIMIT 1
                """
            ),
            {
                "publisher_name": publisher_name.strip(),
                "publisher_like": f"%{publisher_name.strip()}%",
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return int(row["id"])


def resolve_source_author_id_by_name(db: Session, *, author_name: str) -> int | None:
    normalized_name = _normalize_lookup_value(author_name)
    if not normalized_name:
        return None
    row = (
        db.execute(
            text(
                """
                SELECT author.id
                FROM authors AS author
                WHERE lower(author.display_name) = lower(:author_name)
                    OR author.normalized_name = :normalized_name
                    OR author.display_name ILIKE :author_like
                ORDER BY
                    CASE
                        WHEN lower(author.display_name) = lower(:author_name) THEN 0
                        WHEN author.normalized_name = :normalized_name THEN 1
                        ELSE 2
                    END,
                    length(author.display_name) ASC,
                    author.id ASC
                LIMIT 1
                """
            ),
            {
                "author_name": author_name.strip(),
                "normalized_name": normalized_name,
                "author_like": f"%{author_name.strip()}%",
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return int(row["id"])


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
            {'source_id': source_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
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
            {'source_id': source_id},
        )
        .mappings()
        .all()
    )
    company_names, feed_sections = _source_extra_values(extra_rows)
    return RssSourceDetailRead(
        id=int(row['id']),
        title=str(row['title']),
        summary=(str(row['summary']) if row['summary'] is not None else None),
        authors=_parse_source_authors(row['authors']),
        url=_to_public_source_url(row['url']),
        published_at=_to_public_published_at(row['published_at']),
        image_url=_to_public_image_url(row['image_url']),
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
    company_names, feed_sections = _source_extra_values(extra_rows)
    return UserSourceDetailRead(
        id=int(row["id"]),
        title=str(row["title"]),
        summary=(str(row["summary"]) if row["summary"] is not None else None),
        authors=_parse_source_authors(row["authors"]),
        url=_to_public_source_url(row["url"]),
        published_at=_to_public_published_at(row["published_at"]),
        company_names=company_names,
        feed_sections=feed_sections,
    )


def _build_source_filters(
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
        params['feed_id'] = feed_id
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
        params['company_id'] = company_id
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
        params['author_id'] = author_id
    return filters, params


def _build_source_search_filters(
    *,
    language: str | None,
    publisher_id: int | None,
    author_id: int | None,
    published_from: datetime | None,
    published_to: datetime | None,
) -> tuple[list[str], dict[str, object]]:
    filters: list[str] = []
    params: dict[str, object] = {}
    if language:
        filters.append("article.language = :language")
        params["language"] = language
    if publisher_id is not None:
        filters.append(
            """
            (
                article.company_id = :publisher_id
                OR EXISTS (
                    SELECT 1
                    FROM article_feed_links AS link
                    JOIN rss_feeds AS feed
                        ON feed.id = link.feed_id
                    WHERE link.article_id = article.article_id
                        AND feed.company_id = :publisher_id
                )
            )
            """
        )
        params["publisher_id"] = publisher_id
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
    if published_to is not None:
        filters.append("article.published_at <= :published_to")
        params["published_to"] = published_to
    return filters, params


def _to_source_search_candidate(row: object) -> SourceSearchCandidateRead:
    mapping = dict(row)
    return SourceSearchCandidateRead(
        article_id=int(mapping["article_id"]),
        score=float(mapping["score"] or 0.0),
        published_at=_to_public_published_at(mapping["published_at"]),
    )


def _to_public_source_url(value: object) -> str | None:
    if value is None:
        return None
    return normalize_public_http_url(str(value))


def _to_rss_source_read(
    row: object,
    *,
    company_names_by_source_id: dict[int, list[str]],
) -> RssSourceRead:
    mapping = dict(row)
    source_id = int(mapping['id'])
    return RssSourceRead(
        id=source_id,
        title=str(mapping['title']),
        authors=_parse_source_authors(mapping['authors']),
        url=_to_public_source_url(mapping['url']),
        published_at=_to_public_published_at(mapping['published_at']),
        image_url=_to_public_image_url(mapping.get('image_url')),
        company_names=company_names_by_source_id.get(source_id, []),
    )


def _to_user_source_read(
    row: object,
    *,
    company_names_by_source_id: dict[int, list[str]],
) -> UserSourceRead:
    mapping = dict(row)
    source_id = int(mapping["id"])
    return UserSourceRead(
        id=source_id,
        title=str(mapping["title"]),
        authors=_parse_source_authors(mapping["authors"]),
        url=_to_public_source_url(mapping["url"]),
        published_at=_to_public_published_at(mapping["published_at"]),
        company_names=company_names_by_source_id.get(source_id, []),
    )


def _to_user_source_search_item_read(
    row: object,
    *,
    extra_values_by_source_id: dict[int, tuple[list[str], list[str]]],
) -> UserSourceSearchItemRead:
    mapping = dict(row)
    source_id = int(mapping["id"])
    company_names, feed_sections = extra_values_by_source_id.get(source_id, ([], []))
    return UserSourceSearchItemRead(
        id=source_id,
        title=str(mapping["title"]),
        summary=(str(mapping["summary"]) if mapping["summary"] is not None else None),
        authors=_parse_source_authors(mapping["authors"]),
        url=_to_public_source_url(mapping["url"]),
        published_at=_to_public_published_at(mapping["published_at"]),
        company_names=company_names,
        feed_sections=feed_sections,
    )


def _source_extra_values(extra_rows: Sequence[object]) -> tuple[list[str], list[str]]:
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


def _to_public_image_url(value: object) -> str | None:
    if value is None:
        return None
    return normalize_public_http_url(str(value), require_https=True)


def _list_company_names_by_source_ids(db: Session, *, source_ids: Sequence[int]) -> dict[int, list[str]]:
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
            {'source_ids': unique_source_ids},
        )
        .mappings()
        .all()
    )
    company_names_by_source_id: dict[int, list[str]] = {source_id: [] for source_id in unique_source_ids}
    for row in rows:
        source_id = int(row['source_id'])
        company_name = str(row['name'])
        if company_name not in company_names_by_source_id[source_id]:
            company_names_by_source_id[source_id].append(company_name)
    return company_names_by_source_id


def _list_source_extra_values_by_source_ids(
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
        source_id: _source_extra_values(source_rows)
        for source_id, source_rows in rows_by_source_id.items()
    }


def _to_public_published_at(published_at: datetime | None) -> datetime | None:
    normalized = normalize_datetime_to_utc(published_at)
    if normalized is None or normalized == SOURCE_PUBLISHED_AT_FALLBACK:
        return None
    return normalized


def _parse_source_authors(value: object) -> list[RssSourceAuthorRead]:
    if not isinstance(value, list):
        return []

    authors: list[RssSourceAuthorRead] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        author_id = item.get('id')
        author_name = item.get('name')
        if not isinstance(author_id, int):
            continue
        if not isinstance(author_name, str) or not author_name.strip():
            continue
        authors.append(RssSourceAuthorRead(id=author_id, name=author_name))
    return authors


def _normalize_lookup_value(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip())
    normalized = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(normalized.lower().split())
