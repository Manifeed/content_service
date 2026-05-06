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
```

Optional dependencies:

```bash
export QDRANT_URL=http://localhost:6333
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
	manifeed-content-service
```

## Tests

Run all tests:

```bash
pytest -q
```

Current automated coverage validates source compilation, the internal app
bootstrap, readiness, and the shared content-service networking client.

Recommended next tests:

- internal token behavior across environment modes
- route-level tests for source list/detail endpoints
- Qdrant error-handling tests for similar-source queries
- DB integration tests for pagination and detail read models
- icon path validation tests for valid and invalid inputs
