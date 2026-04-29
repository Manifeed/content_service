from __future__ import annotations

from sqlalchemy.orm import Session

from app.errors.app_error import UpstreamServiceError
from app.errors.custom_exceptions import SourceNotFoundError
from app.qdrant.simple_qdrant_client import QdrantIndexingError, SimpleQdrantClient
from app.schemas.analytics.analysis_schema import (
    AnalysisOverviewRead,
    SimilarSourceRead,
    SimilarSourcesRead,
)
from app.sources.database.article_embedding_db_client import (
    count_indexed_embeddings,
    get_article_key_by_id,
)
from app.sources.database.get_sources_db_cli import (
    count_sources,
    get_user_source_detail_read_by_id,
)
from app.sources.domain.source_embedding_config import resolve_source_embedding_worker_version


def read_analysis_overview(db: Session) -> AnalysisOverviewRead:
    qdrant_client = SimpleQdrantClient()
    return AnalysisOverviewRead(
        total_sources=count_sources(db),
        indexed_embeddings=count_indexed_embeddings(db),
        qdrant_collection=qdrant_client.collection_name,
    )


def read_similar_sources(
    db: Session,
    *,
    source_id: int,
    limit: int,
    worker_version: str | None = None,
) -> SimilarSourcesRead:
    source = get_user_source_detail_read_by_id(db, source_id)
    if source is None:
        raise SourceNotFoundError()
    article_key = get_article_key_by_id(db, article_id=source_id)
    if article_key is None:
        raise SourceNotFoundError()

    resolved_worker_version = worker_version or resolve_source_embedding_worker_version()
    try:
        points = SimpleQdrantClient().search_similar_article_embeddings(
            article_key=article_key,
            worker_version=resolved_worker_version,
            limit=limit + 1,
        )
    except QdrantIndexingError as exception:
        raise UpstreamServiceError("Unable to query Qdrant similarity") from exception

    items: list[SimilarSourceRead] = []
    for point in points:
        if point.article_id is None or point.article_id == source_id:
            continue
        similar_source = get_user_source_detail_read_by_id(db, point.article_id)
        if similar_source is None:
            continue
        items.append(
            SimilarSourceRead(
                score=point.score,
                source=similar_source,
            )
        )
        if len(items) >= limit:
            break

    return SimilarSourcesRead(
        source_id=source_id,
        worker_version=resolved_worker_version,
        items=items,
    )
