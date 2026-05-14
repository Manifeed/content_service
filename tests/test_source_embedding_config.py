from __future__ import annotations

from app.domain.source_embedding_config import (
    resolve_embedding_service_api_key,
    resolve_embedding_service_url,
)


def test_resolve_embedding_service_url_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_SERVICE_URL", "http://192.168.4.67:8000")

    assert resolve_embedding_service_url() == "http://192.168.4.67:8000"


def test_resolve_embedding_service_url_uses_safe_default(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_SERVICE_URL", raising=False)

    assert resolve_embedding_service_url() == "http://127.0.0.1:8000"


def test_resolve_embedding_service_api_key_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_SERVICE_API_KEY", "service-key")

    assert resolve_embedding_service_api_key() == "service-key"


def test_resolve_embedding_service_api_key_requires_environment(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_SERVICE_API_KEY", raising=False)

    try:
        resolve_embedding_service_api_key()
    except RuntimeError as exception:
        assert str(exception) == "EMBEDDING_SERVICE_API_KEY is required"
    else:
        raise AssertionError("Expected RuntimeError when EMBEDDING_SERVICE_API_KEY is missing")
