# Architecture

## High-Level Layers

- `app/main.py`: internal-only application bootstrap, logging, and router registration
- `app/database.py`: content DB URL resolution, engine creation, sessions, and readiness check
- `app/routers/internal_content_router.py`: single internal router assembly
- `app/routers`: internal source and analysis HTTP route families
- `app/services`: source read, analysis, and readiness orchestration
- `app/clients/database`: SQL read models and embedding read access
- `app/clients/qdrant`: low-level Qdrant client
- `app/domain`: content identity, embedding, and RSS repository configuration
- `app/utils`: stateless helper functions

## Route Layer

Main route families:

- `/internal/health`: simple liveness endpoint
- `/internal/ready`: strict readiness endpoint for token, content DB, and Qdrant checks
- `/internal/content/admin/sources...`: admin-oriented source reads
- `/internal/content/sources...`: user-oriented source reads
- `/internal/content/analysis...`: analysis overview and similar-source lookup

## Business Layer

Key service modules:

- `app/services/source_admin_service.py`
- `app/services/source_user_service.py`
- `app/services/source_detail_service.py`
- `app/services/analysis_service.py`
- `app/services/readiness_service.py`

These modules keep the route layer thin and isolate SQL/Qdrant behavior from
FastAPI request handling.

## Persistence Layer

Database responsibilities are split by concern:

- `app/database.py`: content session factories and content DB readiness
- `app/clients/database/source_read_database_client.py`: source list/detail read SQL
- `app/clients/database/article_embedding_database_client.py`: embedding metadata SQL

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
