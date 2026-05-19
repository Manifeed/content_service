from __future__ import annotations

from sqlalchemy.orm import Session

from app.clients.database.source_read_database_client import (
    list_user_source_filtered_search_candidates,
)
from app.clients.embedding.source_search_embedder_client import (
    SourceSearchEmbeddingError,
    get_source_search_query_embedder,
)
from app.clients.qdrant.content_qdrant_client import ContentQdrantClient
from app.domain.source_embedding_config import resolve_source_search_dimensions
from app.domain.source_search_query import parse_source_search_query
from app.services.source_search_filters import (
    ResolvedSourceSearchFilters,
    resolve_source_search_filters,
)
from app.services.source_search_page_builder import build_source_search_page
from app.services.source_search_ranking import (
    SourceSearchAggregate,
    rank_vector_candidates,
)

from shared_backend.clients.qdrant_client import QdrantIndexingError
from shared_backend.errors.app_error import UpstreamServiceError
from shared_backend.schemas.sources.source_schema import UserSourceSearchPageRead


def search_user_sources(
    db: Session,
    *,
    q: str | None,
    limit: int,
    offset: int,
    country: str | None,
    language: str | None = None,
    theme: str | None = None,
    company_id: int | None,
    author_id: int | None,
    period: str | None,
) -> UserSourceSearchPageRead:
    parsed_query = parse_source_search_query(q)
    filters = resolve_source_search_filters(
        explicit_country=country,
        explicit_language=language,
        explicit_theme=theme,
        explicit_company_id=company_id,
        explicit_author_id=author_id,
        explicit_period=period,
    )
    subject_query = parsed_query.subject_query

    if not subject_query:
        candidates = list_user_source_filtered_search_candidates(
            db,
            limit=offset + limit + 1,
            country=filters.country,
            language=filters.language,
            themes=filters.themes,
            company_id=filters.company_id,
            author_id=filters.author_id,
            published_from=filters.published_from,
        )
        page_candidates = candidates[offset : offset + limit]
        return build_source_search_page(
            db,
            raw_query=parsed_query.raw_query,
            subject_query=subject_query,
            applied_filters=filters.applied_filters,
            candidates=[
                SourceSearchAggregate(
                    article_id=candidate.article_id,
                    published_at=candidate.published_at,
                )
                for candidate in page_candidates
            ],
            limit=limit,
            offset=offset,
            has_more=len(candidates) > offset + limit,
        )

    pool_size = min(300, offset + limit + 100)
    ranked_candidates = _search_and_rank_vector_candidates(
        subject_query=subject_query,
        limit=pool_size,
        filters=filters,
    )
    return build_source_search_page(
        db,
        raw_query=parsed_query.raw_query,
        subject_query=subject_query,
        applied_filters=filters.applied_filters,
        candidates=ranked_candidates[offset : offset + limit],
        limit=limit,
        offset=offset,
        has_more=len(ranked_candidates) > offset + limit,
    )


def _search_and_rank_vector_candidates(
    *,
    subject_query: str,
    limit: int,
    filters: ResolvedSourceSearchFilters,
) -> list[SourceSearchAggregate]:
    try:
        embedder = get_source_search_query_embedder()
        embedding = embedder.embed_query(subject_query)
        expected_dimensions = resolve_source_search_dimensions()
        if len(embedding.dense) != expected_dimensions:
            raise SourceSearchEmbeddingError(
                f"Query embedding dimension mismatch: expected {expected_dimensions}, got {len(embedding.dense)}"
            )
        qdrant_client = ContentQdrantClient()
        sparse_items = qdrant_client.search_sparse_article_embeddings(
            sparse_indices=embedding.sparse.indices,
            sparse_values=embedding.sparse.values,
            limit=limit,
            country=filters.country,
            language=filters.language,
            themes=filters.themes,
            company_id=filters.company_id,
            author_id=filters.author_id,
            published_from=filters.published_from,
        )
        sparse_article_ids = [item.article_id for item in sparse_items if item.article_id is not None]
        dense_items = qdrant_client.search_dense_article_embeddings(
            dense_vector=embedding.dense,
            limit=limit,
            article_ids=sparse_article_ids or None,
            country=filters.country,
            language=filters.language,
            themes=filters.themes,
            company_id=filters.company_id,
            author_id=filters.author_id,
            published_from=filters.published_from,
        )
    except (SourceSearchEmbeddingError, QdrantIndexingError, RuntimeError) as exception:
        raise UpstreamServiceError("Source search backend is not ready") from exception

    return rank_vector_candidates(
        subject_query=subject_query,
        sparse_items=sparse_items,
        dense_items=dense_items,
    )
