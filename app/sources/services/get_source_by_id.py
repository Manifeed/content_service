from __future__ import annotations

from sqlalchemy.orm import Session

from shared_backend.errors.custom_exceptions import SourceNotFoundError
from shared_backend.schemas.sources.source_schema import RssSourceDetailRead
from app.sources.database.get_sources_db_cli import get_rss_source_detail_read_by_id


def get_rss_source_by_id(
    db: Session,
    *,
    source_id: int,
) -> RssSourceDetailRead:
    payload = get_rss_source_detail_read_by_id(db, source_id)
    if payload is None:
        raise SourceNotFoundError(f"RSS source {source_id} not found")
    return payload
