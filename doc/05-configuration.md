# Configuration

## Core Runtime

- `APP_ENV`
- `ENVIRONMENT`
- `NODE_ENV`
- `CONTENT_DATABASE_URL`
- `CONTENT_READ_DATABASE_URL`
- `DATABASE_URL`
- `IDENTITY_DATABASE_URL`
- `REQUIRE_EXPLICIT_DATABASE_URLS`
- `INTERNAL_SERVICE_TOKEN`
- `REQUIRE_INTERNAL_SERVICE_TOKEN`

Notes:

- `CONTENT_DATABASE_URL` falls back to `CONTENT_READ_DATABASE_URL`
- if still unset, it falls back to `DATABASE_URL`
- an identity DB engine is currently initialized even though the main exposed
  routes are content-oriented

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

## RSS Repository Variables

- `RSS_FEEDS_REPOSITORY_URL`
	- default: `https://github.com/Manifeed/rss_feed`

- `RSS_FEEDS_REPOSITORY_BRANCH`
	- default: `main`

- `RSS_FEEDS_REPOSITORY_PATH`
	- default: `var/rss_feeds`

## HTTP / Browser-Related Variables

- `CORS_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `CSRF_TRUST_SELF_ORIGIN`

## Database Pool Variables

- `DB_POOL_SIZE` (default: `20`)
- `DB_MAX_OVERFLOW` (default: `40`)
- `DB_POOL_TIMEOUT_SECONDS` (default: `30`)
- `DB_POOL_RECYCLE_SECONDS` (default: `1800`)
