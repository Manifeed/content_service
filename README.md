# Manifeed Content Service

`content_service` is the internal read-oriented content service for Manifeed.
It exposes backend-only FastAPI endpoints for source reads, source detail
queries, and Qdrant-backed similar-source lookups.

This service is intended for trusted internal consumers such as `public_api`,
not for browsers or public clients directly.

## What This Service Provides

- Admin-oriented source listing reads
- User-oriented source listing reads
- Source detail reads
- Analysis overview for indexed embeddings
- Similar-source lookup through Qdrant
- Internal token gate (`x-manifeed-internal-token`) on exposed routers

## Architecture Overview

- `app/main.py`: FastAPI bootstrap for the internal-only service
- `app/routers/internal_content_router.py`: single internal router assembly
- `app/database.py`: content database engine, sessions, and readiness check
- `app/routers`: internal route families grouped by feature
- `app/services`: source, analysis, and readiness orchestration
- `app/clients/database`: SQL read models for sources and embeddings
- `app/clients/qdrant`: low-level Qdrant client
- `app/domain`: content identity, embedding, and RSS repository configuration
- `app/utils`: stateless shared helpers

## Quick Start (Local Development)

### 1) Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

### 2) Set a minimal local environment

```bash
export APP_ENV=local
export CONTENT_DATABASE_URL=postgresql://manifeed:manifeed@localhost:5432/manifeed_content
```

Optional dependencies:

```bash
export QDRANT_URL=http://localhost:6333
```

### 3) Run the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Service endpoints include:

- `GET /internal/health`
- `GET /internal/ready`
- `GET /internal/content/admin/sources/...`
- `GET /internal/content/sources/...`
- `GET /internal/content/analysis/...`

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

### Qdrant / analysis

- `QDRANT_URL`
- `QDRANT_COLLECTION_NAME`
- `QDRANT_API_KEY`
- `SOURCE_EMBEDDING_WORKER_VERSION`
- `SOURCE_EMBEDDING_DIMENSIONS`

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

Current tests are limited and mainly cover source compilation.

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
	manifeed-content-service
```

The image is multi-stage, runs as a non-root user, and installs
`shared_backend` from a wheel built locally from the monorepo. The runtime
base image is `python:3.13-slim`.

## Detailed Documentation

Documentation is available in:

- `doc/README.md`
