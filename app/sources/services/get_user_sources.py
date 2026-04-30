from __future__ import annotations

from sqlalchemy.orm import Session

from shared_backend.errors.custom_exceptions import SourceNotFoundError
from shared_backend.schemas.sources.source_schema import UserSourceDetailRead, UserSourcePageRead
from app.sources.database.get_sources_db_cli import (
    get_user_source_detail_read_by_id,
    list_user_sources_read,
)


def get_user_sources(
    db: Session,
    *,
    limit: int,
    offset: int,
) -> UserSourcePageRead:
    items, total = list_user_sources_read(
        db,
        limit=limit,
        offset=offset,
    )
    return UserSourcePageRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_user_source_by_id(
    db: Session,
    *,
    source_id: int,
) -> UserSourceDetailRead:
    payload = get_user_source_detail_read_by_id(db, source_id)
    if payload is None:
        raise SourceNotFoundError(f"RSS source {source_id} not found")
    return payload
