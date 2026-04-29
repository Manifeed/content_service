from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.sources.source_schema import UserSourceDetailRead


class AnalysisOverviewRead(BaseModel):
    total_sources: int = Field(ge=0)
    indexed_embeddings: int = Field(ge=0)
    qdrant_collection: str = Field(min_length=1)


class SimilarSourceRead(BaseModel):
    score: float = Field(ge=0)
    source: UserSourceDetailRead


class SimilarSourcesRead(BaseModel):
    source_id: int = Field(ge=1)
    worker_version: str = Field(min_length=1)
    items: list[SimilarSourceRead] = Field(default_factory=list)
