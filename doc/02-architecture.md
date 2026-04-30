# Architecture

## High-Level Layers

- `main.py`: application bootstrap, logging, middleware, and router registration
- `database.py`: DB URL resolution, engine creation, and session factories
- `app/sources/router`: internal source HTTP route families
- `app/sources/services`: source read business logic
- `app/sources/database`: SQL read models and embedding read access
- `app/analytics`: analysis routes and Qdrant-backed services
- `app/rss`: RSS icon path validation and file serving
- `app/qdrant`: low-level Qdrant client

## Route Layer

Main route families:

- `/internal/health`: simple liveness endpoint
- `/internal/content/admin/sources...`: admin-oriented source reads
- `/internal/content/sources...`: user-oriented source reads
- `/internal/content/analysis...`: analysis overview and similar-source lookup
- `/internal/content/rss/img/...`: RSS icon file reads

## Business Layer

Key service modules:

- `app/sources/services/get_sources.py`
- `app/sources/services/get_user_sources.py`
- `app/sources/services/get_source_by_id.py`
- `app/analytics/services/analysis_service.py`
- `app/rss/services/rss_icon_service.py`

These modules keep the route layer thin and isolate SQL/Qdrant behavior from
FastAPI request handling.

## Persistence Layer

Database responsibilities are split by concern:

- `database.py`: session factories
- `app/sources/database/get_sources_db_cli.py`: source list/detail read SQL
- `app/sources/database/article_embedding_db_client.py`: embedding metadata SQL

## Qdrant Integration Layer

`app/qdrant/simple_qdrant_client.py` encapsulates:

- collection naming and optional API key handling
- point reads and scrolls
- similar-source recommendation queries
- collection initialization helpers used by shared embedding logic

## Error and Schema Strategy

- Exceptions and handlers are imported directly from `shared_backend`
- API contracts are imported directly from `shared_backend` unless a schema has
  service-specific behavior
