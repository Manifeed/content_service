from __future__ import annotations

from app.domain.source_embedding_config import (
    resolve_embedding_service_api_key,
    resolve_embedding_service_url,
)


def test_resolve_embedding_service_url_prefers_canonical_name(monkeypatch) -> None:
    monkeypatch.setenv("BGE_M3_INFERENCE_URL", "http://bge-m3_inference:8000")

    assert resolve_embedding_service_url() == "http://bge-m3_inference:8000"


def test_resolve_embedding_service_api_key_reads_canonical_name(monkeypatch) -> None:
    monkeypatch.setenv("BGE_M3_INFERENCE_API_KEY", "canonical-key")

    assert resolve_embedding_service_api_key() == "canonical-key"
