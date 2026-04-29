# Manifeed Content Service

`content_service` is the internal read-oriented content service for Manifeed.
It exposes backend-only FastAPI endpoints for source reads, source detail
queries, Qdrant-backed similar-source lookups, and RSS icon file reads.

This service is intended for trusted internal consumers such as `public_api`,
not for browsers or public clients directly.

## What This Service Provides

- Admin-oriented source listing reads
- User-oriented source listing reads
- Source detail reads
- Analysis overview for indexed embeddings
- Similar-source lookup through Qdrant
- RSS icon SVG reads from the local RSS repository
- Internal token gate (`x-manifeed-internal-token`) on exposed routers

## Architecture Overview

- `app/sources/router`: internal content route families
- `app/sources/services`: source read business layer
- `app/sources/database`: SQL read models for sources and embeddings
- `app/analytics`: analysis overview and Qdrant similarity routes
- `app/rss`: RSS icon path validation and file serving
- `app/qdrant`: low-level Qdrant client
- `database.py`: SQLAlchemy engine and session factories

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
export RSS_FEEDS_REPOSITORY_PATH=var/rss_feeds
```

### 3) Run the API

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Service endpoints include:

- `GET /internal/health`
- `GET /internal/content/admin/sources/...`
- `GET /internal/content/sources/...`
- `GET /internal/content/analysis/...`
- `GET /internal/content/rss/img/{icon_url}`

## Security Model

- Internal routers rely on `x-manifeed-internal-token` authorization.
- Local/test-like environments may allow missing token when not explicitly
  forced into strict mode.
- Qdrant access can use an optional API key.
- RSS icon path resolution rejects traversal and non-SVG files.
- CSRF origin checks are present for unsafe `/api/*` calls, although this
  service mainly exposes `/internal/*` routes.

## Configuration

### Core runtime

- `APP_ENV` / `ENVIRONMENT` / `NODE_ENV`
- `CONTENT_DATABASE_URL`
- `CONTENT_READ_DATABASE_URL`
- `DATABASE_URL`
- `IDENTITY_DATABASE_URL`
- `REQUIRE_EXPLICIT_DATABASE_URLS`
- `INTERNAL_SERVICE_TOKEN`
- `REQUIRE_INTERNAL_SERVICE_TOKEN`

### Qdrant / analysis

- `QDRANT_URL`
- `QDRANT_COLLECTION_NAME`
- `QDRANT_API_KEY`
- `SOURCE_EMBEDDING_WORKER_VERSION`
- `SOURCE_EMBEDDING_DIMENSIONS`

### RSS icons / local repository

- `RSS_FEEDS_REPOSITORY_URL`
- `RSS_FEEDS_REPOSITORY_BRANCH`
- `RSS_FEEDS_REPOSITORY_PATH`

### HTTP / browser-related settings

- `CORS_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `CSRF_TRUST_SELF_ORIGIN`

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

Build:

```bash
docker build -t manifeed-content-service -f content_service/Dockerfile content_service
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

## Detailed Documentation

Documentation is available in:

- `doc/README.md`
