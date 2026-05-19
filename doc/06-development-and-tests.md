# Development and Testing

## Local Setup

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Minimum local environment:

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

Run the service:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

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
	-e EMBEDDING_SERVICE_API_KEY='replace-me' \
	manifeed-content-service
```

## Tests

Run all tests:

```bash
pytest -q
```

Current automated coverage includes:

- `tests/test_source_syntax.py`: Python syntax validation
- `tests/test_file_sizes.py`: file-size guardrails
- `tests/test_source_embedding_config.py`: embedding URL and dimension resolution
- `tests/test_source_search.py`: search query normalization and ranking helpers
- `tests/test_internal_content_app.py`: internal app bootstrap, readiness, and search route wiring

Shared networking contracts for this service are also covered in
`shared_backend/tests/test_content_service_networking_client.py`.

## Runtime Base

The container build targets `python:3.13-slim`.

Recommended next tests:

- internal token behavior across environment modes
- route-level tests for source list/detail endpoints with mocked DB rows
- Qdrant and embedding error-handling tests for search and similar-source queries
- DB integration tests for pagination and detail read models
