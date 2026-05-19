# Manifeed Content Service

`content_service` is the internal read-oriented content service for Manifeed.
It exposes backend-only FastAPI endpoints for user source reads, semantic source
search, and Qdrant-backed similar-source lookups.

This service is intended for trusted internal consumers such as `public_api`,
not for browsers or public clients directly.

## What This Service Provides

- User-oriented source listing reads
- Semantic source search (`/internal/content/sources/search`)
- Source detail reads
- Similar-source lookup through Qdrant
- Internal token gate (`x-manifeed-internal-token`) on exposed routers

Admin-oriented source reads live in `admin_service`.

## Architecture Overview

- `app/main.py`: FastAPI bootstrap for the internal-only service
- `app/routers/internal_content_router.py`: internal router assembly
- `app/routers/user_source_router.py`: source list, search, detail, and similar routes
- `app/database.py`: content database engine, sessions, and readiness check
- `app/services`: source, search, analysis, and readiness orchestration
- `app/clients/database`: SQL read models for sources
- `app/clients/embedding`: query embedding client for semantic search
- `app/clients/qdrant`: low-level Qdrant client
- `app/domain`: search query parsing and embedding configuration

## Quick Start (Local Development)

### 1) Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

### 2) Set a minimal local environment

```bash
export APP_ENV=local
export CONTENT_DATABASE_URL=postgresql://manifeed:manifeed@localhost:5432/manifeed_content
export INTERNAL_SERVICE_TOKEN='replace-with-strong-secret-min-32-chars'
```

Optional dependencies:

```bash
export QDRANT_URL=http://localhost:6333
export EMBEDDING_SERVICE_URL=http://127.0.0.1:8000
export EMBEDDING_SERVICE_API_KEY='replace-me'
```

### 3) Run the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Service endpoints include:

- `GET /internal/health`
- `GET /internal/ready`
- `GET /internal/content/sources/`
- `GET /internal/content/sources/search`
- `GET /internal/content/sources/{source_id}`
- `GET /internal/content/sources/{source_id}/similar`

## Security Model

- Internal routers rely on `x-manifeed-internal-token` authorization.
- Local/test-like environments may allow missing token when not explicitly
  forced into strict mode.
- Qdrant access can use an optional API key.
- Browser-facing CORS and CSRF checks belong to `public_api`; this service
  exposes only internal routes.

## Configuration

### Core runtime

- `APP_ENV` / `ENVIRONMENT` / `NODE_ENV`
- `CONTENT_DATABASE_URL`
- `CONTENT_READ_DATABASE_URL`
- `DATABASE_URL`
- `REQUIRE_EXPLICIT_DATABASE_URLS`
- `INTERNAL_SERVICE_TOKEN`
- `REQUIRE_INTERNAL_SERVICE_TOKEN`

### Search / embeddings / Qdrant

- `QDRANT_URL`
- `QDRANT_COLLECTION_NAME`
- `QDRANT_API_KEY`
- `EMBEDDING_SERVICE_URL`
- `EMBEDDING_SERVICE_API_KEY`
- `SOURCE_EMBEDDING_WORKER_VERSION`
- `SOURCE_EMBEDDING_DIMENSIONS`
- `SOURCE_SEARCH_RECENCY_HALFLIFE_DAYS`

### DB pool tuning

- `DB_POOL_SIZE`: SQLAlchemy pool size (`20`)
- `DB_MAX_OVERFLOW`: SQLAlchemy max overflow (`40`)
- `DB_POOL_TIMEOUT_SECONDS`: pool checkout timeout (`30`)
- `DB_POOL_RECYCLE_SECONDS`: pool recycle interval (`1800`)

## Tests

Run the current test suite:

```bash
pytest -q
```

Coverage includes source search ranking, embedding configuration, internal app
bootstrap/readiness, file-size guardrails, and shared networking contracts.

## Docker

Build from the monorepo root:

```bash
docker build -t manifeed-content-service -f content_service/Dockerfile .
```

Run:

```bash
docker run --rm -p 8000:8000 \
	-e APP_ENV=production \
	-e CONTENT_DATABASE_URL='postgresql://user:pass@content-host:5432/content' \
	-e INTERNAL_SERVICE_TOKEN='replace-with-strong-secret-min-32-chars' \
	-e QDRANT_URL='http://qdrant:6333' \
	-e EMBEDDING_SERVICE_API_KEY='replace-me' \
	manifeed-content-service
```

The image is multi-stage, runs as a non-root user, and installs
`shared_backend` from a wheel built locally from the monorepo. The runtime
base image is `python:3.13-slim`.

## Detailed Documentation

Documentation is available in:

- `doc/README.md`
