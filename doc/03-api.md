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

## User-Oriented Source Reads

Routes below are exposed under `/internal/content/sources` and require
internal token authorization.

### `GET /internal/content/sources/`

Lists user-facing source payloads.

Parameters:

- `limit`
- `offset`

### `GET /internal/content/sources/search`

Runs semantic source search.

Parameters:

- `q`
- `limit`
- `offset`
- `country`
- `company_id`
- `author_id`
- `period` (`all`, `1h`, `24h`, `7d`, `1m`, `1y`)

Unknown query parameters are rejected with `422`.

### `GET /internal/content/sources/{source_id}`

Returns a user-facing source detail payload.

### `GET /internal/content/sources/{source_id}/similar`

Returns similar sources for a given source ID.

Parameters:

- `limit`

## Runtime Flows

### Source Read Flow

1. validate internal token through parent router
2. validate pagination and path parameters
3. execute SQL read model query
4. map DB rows to schema payloads
5. return page or detail response

### Source Search Flow

1. validate internal token
2. parse and normalize the search query
3. embed the query through the embedding service
4. query Qdrant and hydrate SQL metadata for candidates
5. rank and paginate matches
6. return `UserSourceSearchPageRead`

### Similar Source Flow

1. validate internal token
2. load source existence from Postgres
3. resolve article key
4. query Qdrant recommendations
5. hydrate similar article IDs back into source detail payloads
6. return ordered similarity items
