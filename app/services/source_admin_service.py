from __future__ import annotations

from sqlalchemy.orm import Session

from app.clients.database.source_read_database_client import list_rss_sources_read

from shared_backend.schemas.sources.source_schema import RssSourcePageRead


def get_rss_sources(
    db: Session,
    *,
    limit: int,
    offset: int,
    feed_id: int | None = None,
    company_id: int | None = None,
    author_id: int | None = None,
) -> RssSourcePageRead:
    items, total = list_rss_sources_read(
        db,
        limit=limit,
        offset=offset,
        feed_id=feed_id,
        company_id=company_id,
        author_id=author_id,
    )
    return RssSourcePageRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
