# API Reference

## Health Endpoint

### `GET /internal/health`

Simple liveness endpoint.

Response:

```json
{
	"service": "content-service",
	"status": "ok"
}
```

### `GET /internal/ready`

Strict readiness endpoint. It validates internal-service token configuration,
content database connectivity, and Qdrant availability.

Response:

```json
{
	"service": "content-service",
	"status": "ready"
}
```

## Admin-Oriented Source Reads

Routes below are exposed under `/internal/content/admin/sources` and require
internal token authorization.

### `GET /internal/content/admin/sources/`

Lists RSS sources.

Supported parameters:

- `limit`
- `offset`
- `author_id`

### `GET /internal/content/admin/sources/feeds/{feed_id}`

Lists RSS sources filtered by feed.

### `GET /internal/content/admin/sources/companies/{company_id}`

Lists RSS sources filtered by company.

### `GET /internal/content/admin/sources/{source_id}`

Returns an RSS source detail payload.

## User-Oriented Source Reads

Routes below are exposed under `/internal/content/sources`.

### `GET /internal/content/sources/`

Lists user-facing source payloads.

Parameters:

- `limit`
- `offset`

### `GET /internal/content/sources/{source_id}`

Returns a user-facing source detail payload.

### `GET /internal/content/sources/{source_id}/similar`

Returns similar sources for a given source ID.

Parameters:

- `limit`

## Analysis Endpoints

### `GET /internal/content/analysis/overview`

Returns:

- total source count
- indexed embedding count
- Qdrant collection name

### `GET /internal/content/analysis/similar-sources`

Returns similar sources for a given `source_id`.

Parameters:

- `source_id`
- `limit`

## Runtime Flows

### Source Read Flow

1. validate internal token through parent router
2. validate pagination and path parameters
3. execute SQL read model query
4. map DB rows to schema payloads
5. return page or detail response

### Similar Source Flow

1. validate internal token
2. load source existence from Postgres
3. resolve article key
4. query Qdrant recommendations
5. hydrate similar article IDs back into source detail payloads
6. return ordered similarity items
