from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def content_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("CONTENT_READ_DATABASE_URL", "postgresql://user:pass@localhost:5432/content")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "x" * 32)

    app_database = importlib.import_module("app.database")
    app_main = importlib.import_module("app.main")
    admin_source_router = importlib.import_module("app.routers.admin_source_router")
    user_source_router = importlib.import_module("app.routers.user_source_router")

    app = app_main.create_app()

    def override_content_db_session() -> Iterator[object]:
        yield object()

    app.dependency_overrides[app_database.get_content_read_db_session] = override_content_db_session

    monkeypatch.setattr(app_main, "check_content_database_ready", lambda: None)
    monkeypatch.setattr(app_main, "check_qdrant_ready", lambda: None)
    monkeypatch.setattr(app_main, "check_source_search_embedder_ready", lambda: None)
    monkeypatch.setattr(
        admin_source_router,
        "get_rss_sources",
        lambda db, *, limit, offset, author_id, feed_id=None, company_id=None: {
            "items": [
                {
                    "id": 11,
                    "title": "Admin source",
                    "authors": [],
                    "url": "https://example.com/source",
                    "published_at": datetime.now(timezone.utc),
                    "company_names": ["ACME"],
                    "image_url": None,
                }
            ],
            "total": 1,
            "limit": limit,
            "offset": offset,
        },
    )
    monkeypatch.setattr(
        user_source_router,
        "search_user_sources",
        lambda db, **kwargs: {
            "raw_query": kwargs["q"] or "",
            "subject_query": kwargs["q"] or "",
            "applied_filters": [],
            "items": [],
            "limit": kwargs["limit"],
            "offset": kwargs["offset"],
            "has_more": False,
        },
    )
    return app


def test_internal_health_and_ready(content_app) -> None:
    with TestClient(content_app) as client:
        health_response = client.get("/internal/health")
        ready_response = client.get("/internal/ready")

    assert health_response.status_code == 200
    assert health_response.json() == {"service": "content-service", "status": "ok"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"service": "content-service", "status": "ready"}


def test_internal_router_serves_admin_sources(content_app) -> None:
    with TestClient(content_app) as client:
        response = client.get(
            "/internal/content/admin/sources/",
            params={"limit": 10, "offset": 5, "author_id": 3},
            headers={"x-manifeed-internal-token": "x" * 32},
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == 11
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 5


def test_internal_router_serves_source_search(content_app) -> None:
    with TestClient(content_app) as client:
        response = client.get(
            "/internal/content/sources/search",
            params={"q": "finance", "limit": 12, "offset": 6},
            headers={"x-manifeed-internal-token": "x" * 32},
        )

    assert response.status_code == 200
    assert response.json()["raw_query"] == "finance"
    assert response.json()["limit"] == 12
    assert response.json()["offset"] == 6


def test_internal_source_search_rejects_removed_language_filter(content_app) -> None:
    with TestClient(content_app) as client:
        response = client.get(
            "/internal/content/sources/search",
            params={"q": "finance", "language": "fr"},
            headers={"x-manifeed-internal-token": "x" * 32},
        )

    assert response.status_code == 422
