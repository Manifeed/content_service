from __future__ import annotations

from datetime import datetime, timezone

from shared_backend.schemas.sources.source_schema import (
    RssSourceAuthorRead,
    RssSourceRead,
    UserSourceRead,
    UserSourceSearchItemRead,
)
from shared_backend.utils.datetime_utils import normalize_datetime_to_utc
from shared_backend.utils.public_url import normalize_public_http_url


SOURCE_PUBLISHED_AT_FALLBACK = datetime(1970, 1, 1, tzinfo=timezone.utc)


def to_public_source_url(value: object) -> str | None:
    if value is None:
        return None
    return normalize_public_http_url(str(value))


def to_public_image_url(value: object) -> str | None:
    if value is None:
        return None
    return normalize_public_http_url(str(value), require_https=True)


def to_public_published_at(published_at: datetime | None) -> datetime | None:
    normalized = normalize_datetime_to_utc(published_at)
    if normalized is None or normalized == SOURCE_PUBLISHED_AT_FALLBACK:
        return None
    return normalized


def parse_source_authors(value: object) -> list[RssSourceAuthorRead]:
    if not isinstance(value, list):
        return []
    authors: list[RssSourceAuthorRead] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        author_id = item.get("id")
        author_name = item.get("name")
        if not isinstance(author_id, int):
            continue
        if not isinstance(author_name, str) or not author_name.strip():
            continue
        authors.append(RssSourceAuthorRead(id=author_id, name=author_name))
    return authors


def to_rss_source_read(
    row: object,
    *,
    company_names_by_source_id: dict[int, list[str]],
) -> RssSourceRead:
    mapping = dict(row)
    source_id = int(mapping["id"])
    return RssSourceRead(
        id=source_id,
        title=str(mapping["title"]),
        authors=parse_source_authors(mapping["authors"]),
        url=to_public_source_url(mapping["url"]),
        published_at=to_public_published_at(mapping["published_at"]),
        image_url=to_public_image_url(mapping.get("image_url")),
        company_names=company_names_by_source_id.get(source_id, []),
    )


def to_user_source_read(
    row: object,
    *,
    company_names_by_source_id: dict[int, list[str]],
) -> UserSourceRead:
    mapping = dict(row)
    source_id = int(mapping["id"])
    return UserSourceRead(
        id=source_id,
        title=str(mapping["title"]),
        authors=parse_source_authors(mapping["authors"]),
        url=to_public_source_url(mapping["url"]),
        published_at=to_public_published_at(mapping["published_at"]),
        company_names=company_names_by_source_id.get(source_id, []),
    )


def to_user_source_search_item_read(
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
        authors=parse_source_authors(mapping["authors"]),
        url=to_public_source_url(mapping["url"]),
        published_at=to_public_published_at(mapping["published_at"]),
        company_names=company_names,
        feed_sections=feed_sections,
    )
