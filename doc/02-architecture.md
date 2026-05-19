# Architecture

## High-Level Layers

- `app/main.py`: internal-only application bootstrap, logging, and router registration
- `app/database.py`: content DB URL resolution, engine creation, sessions, and readiness check
- `app/routers/internal_content_router.py`: single internal router assembly
- `app/routers/user_source_router.py`: source list, search, detail, and similar routes
- `app/services`: source read, search, analysis, and readiness orchestration
- `app/clients/database`: SQL read models for sources
- `app/clients/embedding`: query embedding client for semantic search
- `app/clients/qdrant`: low-level Qdrant client
- `app/domain`: search query parsing and embedding configuration

## Route Layer

Main route families:

- `/internal/health`: simple liveness endpoint
- `/internal/ready`: strict readiness endpoint for token, content DB, and Qdrant checks
- `/internal/content/sources/...`: user-oriented source reads and search
- `/internal/content/sources/{source_id}/similar`: similar-source lookup

## Business Layer

Key service modules:

- `app/services/source_user_service.py`
- `app/services/source_search_service.py`
- `app/services/source_search_filters.py`
- `app/services/source_search_page_builder.py`
- `app/services/source_search_ranking.py`
- `app/services/analysis_service.py`
- `app/services/readiness_service.py`

These modules keep the route layer thin and isolate SQL, embedding, and Qdrant
behavior from FastAPI request handling.

## Persistence Layer

Database responsibilities are split by concern:

- `app/database.py`: content session factories and content DB readiness
- `app/clients/database/source_read_database_client.py`: facade over list/detail/search SQL helpers
- `app/clients/database/source_read_*_database_client.py`: focused SQL read modules
- `app/clients/database/source_read_support.py` and `source_read_mappers.py`: shared SQL helpers

## Qdrant Integration Layer

`app/clients/qdrant/content_qdrant_client.py` encapsulates:

- collection naming and optional API key handling
- point reads and scrolls
- similar-source recommendation queries
- collection initialization helpers used by shared embedding logic

## Error and Schema Strategy

- Exceptions and handlers are imported directly from `shared_backend`
- API contracts are imported directly from `shared_backend` unless a schema has
  service-specific behavior
