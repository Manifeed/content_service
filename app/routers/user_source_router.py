from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_content_read_db_session
from app.services.analysis_service import read_similar_sources
from app.services.source_user_service import get_user_source_by_id, get_user_sources

from shared_backend.security.internal_service_auth import require_internal_service_token
from shared_backend.schemas.analytics.analysis_schema import SimilarSourcesRead
from shared_backend.schemas.sources.source_schema import UserSourceDetailRead, UserSourcePageRead


user_sources_router = APIRouter(
    prefix="/internal/content/sources",
    tags=["sources"],
    dependencies=[Depends(require_internal_service_token)],
)


@user_sources_router.get("/", response_model=UserSourcePageRead)
def read_user_sources(
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_content_read_db_session),
) -> UserSourcePageRead:
    return get_user_sources(db, limit=limit, offset=offset)


@user_sources_router.get("/{source_id}", response_model=UserSourceDetailRead)
def read_user_source_by_id(
    source_id: int = Path(ge=1),
    db: Session = Depends(get_content_read_db_session),
) -> UserSourceDetailRead:
    return get_user_source_by_id(db, source_id=source_id)


@user_sources_router.get("/{source_id}/similar", response_model=SimilarSourcesRead)
def read_user_source_similar(
    source_id: int = Path(ge=1),
    limit: int = Query(default=10, ge=1, le=20),
    worker_version: str | None = Query(default=None, min_length=1, max_length=80),
    db: Session = Depends(get_content_read_db_session),
) -> SimilarSourcesRead:
    return read_similar_sources(
        db,
        source_id=source_id,
        limit=limit,
        worker_version=worker_version,
    )
