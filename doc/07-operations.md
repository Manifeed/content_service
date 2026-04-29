# Operations

## Production Recommendations

- set `APP_ENV=production` (or explicit staging value)
- configure strong `INTERNAL_SERVICE_TOKEN` (minimum 32 characters)
- set explicit `CONTENT_DATABASE_URL`
- configure `QDRANT_URL` and `QDRANT_COLLECTION_NAME` explicitly
- monitor source query latency and Qdrant failure rate
- keep RSS repository path stable and readable if icon serving is enabled

## Known Constraints

- `/internal/health` is only a liveness endpoint and does not verify Postgres or Qdrant
- inter-service auth still relies on a shared secret token
- the service currently initializes an identity DB engine that is not clearly used by exposed routes
- Qdrant requests use short-lived HTTP clients unless a client is injected
- Docker runtime still uses a broad default base image setup

## Suggested Monitoring

- API latency on source list and source detail endpoints
- Qdrant query failures and latency
- Postgres pool saturation
- error rates for source-not-found and upstream Qdrant failures
- filesystem errors for RSS icon reads

## Documentation Maintenance

Update docs in this folder whenever behavior changes in:

- `main.py`
- `database.py`
- `app/sources/router/*`
- `app/sources/services/*`
- `app/sources/database/*`
- `app/analytics/*`
- `app/rss/*`
- `app/internal/security.py`
