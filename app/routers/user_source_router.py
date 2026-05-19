from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

from app.database import get_content_read_db_session
from app.services.analysis_service import read_similar_sources
from app.services.source_search_service import search_user_sources
from app.services.source_user_service import get_user_source_by_id, get_user_sources

from shared_backend.security.internal_service_auth import require_internal_service_token
from shared_backend.schemas.analytics.analysis_schema import SimilarSourcesRead
from shared_backend.schemas.sources.source_schema import (
    UserSourceDetailRead,
    UserSourcePageRead,
    UserSourceSearchPageRead,
)

_SOURCE_SEARCH_QUERY_PARAMS = {
    "q",
    "limit",
    "offset",
    "country",
    "language",
    "theme",
    "company_id",
    "author_id",
    "period",
}


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


@user_sources_router.get("/search", response_model=UserSourceSearchPageRead)
def search_user_source_articles(
    request: Request,
    q: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    language: str | None = Query(default=None, min_length=2, max_length=2),
    theme: str | None = Query(default=None, max_length=120),
    company_id: int | None = Query(default=None, ge=1),
    author_id: int | None = Query(default=None, ge=1),
    period: str | None = Query(
        default="all",
        pattern="^(all|ALL|1h|1H|24h|24H|7d|7D|1m|1M|1y|1Y)$",
    ),
    db: Session = Depends(get_content_read_db_session),
) -> UserSourceSearchPageRead:
    _reject_unknown_search_params(request)
    return search_user_sources(
        db,
        q=q,
        limit=limit,
        offset=offset,
        country=country,
        language=language,
        theme=theme,
        company_id=company_id,
        author_id=author_id,
        period=period,
    )


def _reject_unknown_search_params(request: Request) -> None:
    unknown_params = sorted(set(request.query_params) - _SOURCE_SEARCH_QUERY_PARAMS)
    if unknown_params:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported search query parameter(s): {', '.join(unknown_params)}",
        )


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
    db: Session = Depends(get_content_read_db_session),
) -> SimilarSourcesRead:
    return read_similar_sources(
        db,
        source_id=source_id,
        limit=limit,
    )
