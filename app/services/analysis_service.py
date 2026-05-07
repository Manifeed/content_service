from __future__ import annotations

from sqlalchemy.orm import Session

from app.clients.qdrant.content_qdrant_client import QdrantIndexingError, ContentQdrantClient
from app.clients.database.article_embedding_database_client import count_indexed_embeddings
from app.clients.database.source_read_database_client import (
    count_sources,
    get_user_source_detail_read_by_id,
)
from app.domain.source_embedding_config import resolve_source_embedding_model_name

from shared_backend.errors.app_error import UpstreamServiceError
from shared_backend.errors.custom_exceptions import SourceNotFoundError
from shared_backend.schemas.analytics.analysis_schema import (
    AnalysisOverviewRead,
    SimilarSourceRead,
    SimilarSourcesRead,
)


def read_analysis_overview(db: Session) -> AnalysisOverviewRead:
    qdrant_client = ContentQdrantClient()
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
) -> SimilarSourcesRead:
    source = get_user_source_detail_read_by_id(db, source_id)
    if source is None:
        raise SourceNotFoundError()

    try:
        points = ContentQdrantClient().search_similar_article_embeddings(
            article_id=source_id,
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
        model_name=resolve_source_embedding_model_name(),
        items=items,
    )
