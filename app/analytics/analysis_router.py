from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.services.analysis_service import (
    read_analysis_overview,
    read_similar_sources,
)
from app.internal.security import require_internal_service_token
from app.schemas.analytics.analysis_schema import AnalysisOverviewRead, SimilarSourcesRead
from database import get_content_db_session


analysis_router = APIRouter(
    prefix="/internal/content/analysis",
    tags=["analysis"],
    dependencies=[Depends(require_internal_service_token)],
)


@analysis_router.get("/overview", response_model=AnalysisOverviewRead)
def read_analysis_overview_route(
    db: Session = Depends(get_content_db_session),
) -> AnalysisOverviewRead:
    return read_analysis_overview(db)


@analysis_router.get("/similar-sources", response_model=SimilarSourcesRead)
def read_similar_sources_route(
    source_id: int = Query(ge=1),
    limit: int = Query(default=10, ge=1, le=20),
    worker_version: str | None = Query(default=None, min_length=1, max_length=80),
    db: Session = Depends(get_content_db_session),
) -> SimilarSourcesRead:
    return read_similar_sources(
        db,
        source_id=source_id,
        limit=limit,
        worker_version=worker_version,
    )
