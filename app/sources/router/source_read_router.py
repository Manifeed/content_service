from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.schemas.sources.source_schema import RssSourceDetailRead, RssSourcePageRead
from app.sources.services.get_source_by_id import get_rss_source_by_id
from app.sources.services.get_sources import get_rss_sources
from database import get_content_db_session


source_read_router = APIRouter(tags=["sources-read"])


@source_read_router.get("/", response_model=RssSourcePageRead)
def read_sources(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    author_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_content_db_session),
) -> RssSourcePageRead:
    return get_rss_sources(db, limit=limit, offset=offset, author_id=author_id)


@source_read_router.get("/feeds/{feed_id}", response_model=RssSourcePageRead)
def read_sources_by_feed(
    feed_id: int = Path(ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    author_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_content_db_session),
) -> RssSourcePageRead:
    return get_rss_sources(db, limit=limit, offset=offset, feed_id=feed_id, author_id=author_id)


@source_read_router.get("/companies/{company_id}", response_model=RssSourcePageRead)
def read_sources_by_company(
    company_id: int = Path(ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    author_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_content_db_session),
) -> RssSourcePageRead:
    return get_rss_sources(db, limit=limit, offset=offset, company_id=company_id, author_id=author_id)


@source_read_router.get("/{source_id}", response_model=RssSourceDetailRead)
def read_source_by_id(
    source_id: int = Path(ge=1),
    db: Session = Depends(get_content_db_session),
) -> RssSourceDetailRead:
    return get_rss_source_by_id(db, source_id=source_id)
