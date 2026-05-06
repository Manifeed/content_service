# Configuration

## Core Runtime

- `APP_ENV`
- `ENVIRONMENT`
- `NODE_ENV`
- `CONTENT_DATABASE_URL`
- `CONTENT_READ_DATABASE_URL`
- `DATABASE_URL`
- `REQUIRE_EXPLICIT_DATABASE_URLS`
- `INTERNAL_SERVICE_TOKEN`
- `REQUIRE_INTERNAL_SERVICE_TOKEN`

Notes:

- `CONTENT_DATABASE_URL` falls back to `CONTENT_READ_DATABASE_URL`
- if still unset, it falls back to `DATABASE_URL`
- `content_service` only initializes the content database; identity data stays
  behind the identity/user services

## Qdrant / Analysis Variables

- `QDRANT_URL`
	- default: `http://qdrant:6333`

- `QDRANT_COLLECTION_NAME`
	- default: `article_embeddings`

- `QDRANT_API_KEY`
	- optional

- `SOURCE_EMBEDDING_WORKER_VERSION`
	- default: `e5-large-v1`

- `SOURCE_EMBEDDING_DIMENSIONS`
	- optional integer override

## Database Pool Variables

- `DB_POOL_SIZE` (default: `20`)
- `DB_MAX_OVERFLOW` (default: `40`)
- `DB_POOL_TIMEOUT_SECONDS` (default: `30`)
- `DB_POOL_RECYCLE_SECONDS` (default: `1800`)
