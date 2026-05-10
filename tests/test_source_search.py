from __future__ import annotations

from datetime import UTC, datetime

from app.clients.qdrant.content_qdrant_client import build_qdrant_source_search_filter
from app.domain.source_search_query import (
    build_e5_query_input,
    normalize_search_query,
    normalize_embedding_vector,
    parse_source_search_query,
)
from app.clients.qdrant.content_qdrant_client import QdrantScoredArticleEmbeddingPointRead
from app.services.source_search_service import _rank_vector_candidates


def test_source_search_parser_keeps_filter_words_as_subject() -> None:
    parsed = parse_source_search_query("articles français publiés par Le Monde")

    assert parsed.subject_query == "articles français publiés par le monde"


def test_source_search_parser_keeps_subject_queries() -> None:
    assert parse_source_search_query("finance").subject_query == "finance"
    assert (
        parse_source_search_query("marché obligataire en Europe").subject_query
        == "marché obligataire en europe"
    )
    assert (
        parse_source_search_query("dernier résultat financier de Nvidia").subject_query
        == "dernier résultat financier de nvidia"
    )


def test_source_search_parser_does_not_extract_author_or_date() -> None:
    parsed = parse_source_search_query("articles écrits par Ada Lovelace après janvier 2026")

    assert parsed.subject_query == "articles écrits par ada lovelace après janvier 2026"


def test_query_embedder_input_and_normalization_contract() -> None:
    assert build_e5_query_input("  finance   durable ") == "query: finance durable"
    assert (
        normalize_search_query("Nvidia")
        == normalize_search_query("nvidia")
        == normalize_search_query("NVIDIA")
    )

    vector = normalize_embedding_vector([3.0, 4.0])

    assert vector == [0.6, 0.8]


def test_qdrant_source_search_filter_contract() -> None:
    payload = build_qdrant_source_search_filter(
        article_ids=[2, 1, 2],
        country="fr",
        company_id=12,
        author_id=7,
        published_from=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert payload == {
        "must": [
            {"has_id": [1, 2]},
            {"key": "country", "match": {"value": "fr"}},
            {"key": "company_id", "match": {"value": 12}},
            {"key": "author_ids", "match": {"value": 7}},
            {
                "key": "published_at",
                "range": {
                    "gte": "2026-01-01T00:00:00+00:00",
                },
            },
        ]
    }


def test_vector_ranking_keeps_only_confirmed_topic_matches() -> None:
    sparse = [
        QdrantScoredArticleEmbeddingPointRead(
            point_id="1",
            article_id=1,
            article_key="a",
            model_name="BAAI/bge-m3",
            score=0.9,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        QdrantScoredArticleEmbeddingPointRead(
            point_id="2",
            article_id=2,
            article_key="b",
            model_name="BAAI/bge-m3",
            score=0.8,
            published_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
    ]
    dense = [
        QdrantScoredArticleEmbeddingPointRead(
            point_id="2",
            article_id=2,
            article_key="b",
            model_name="BAAI/bge-m3",
            score=0.4,
            published_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
        QdrantScoredArticleEmbeddingPointRead(
            point_id="3",
            article_id=3,
            article_key="c",
            model_name="BAAI/bge-m3",
            score=0.3,
            published_at=datetime(2026, 3, 1, tzinfo=UTC),
        ),
    ]

    result = _rank_vector_candidates(sparse_items=sparse, dense_items=dense)

    assert [candidate.article_id for candidate in result] == [2]
    assert result[0].matched_by == {"sparse", "dense"}


def test_vector_ranking_prioritizes_date_after_relevance_gate() -> None:
    sparse = [
        QdrantScoredArticleEmbeddingPointRead(
            point_id="1",
            article_id=1,
            article_key="a",
            model_name="BAAI/bge-m3",
            score=0.7,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        QdrantScoredArticleEmbeddingPointRead(
            point_id="2",
            article_id=2,
            article_key="b",
            model_name="BAAI/bge-m3",
            score=0.7,
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
        ),
    ]
    dense = [
        QdrantScoredArticleEmbeddingPointRead(
            point_id="1",
            article_id=1,
            article_key="a",
            model_name="BAAI/bge-m3",
            score=0.7,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        QdrantScoredArticleEmbeddingPointRead(
            point_id="2",
            article_id=2,
            article_key="b",
            model_name="BAAI/bge-m3",
            score=0.7,
            published_at=datetime(2026, 5, 1, tzinfo=UTC),
        ),
    ]

    result = _rank_vector_candidates(
        subject_query="finance durable marche europe",
        sparse_items=sparse,
        dense_items=dense,
    )

    assert [candidate.article_id for candidate in result] == [2, 1]
