# Security

## Internal Service Authentication

Header used for internal authorization:

- `x-manifeed-internal-token`

Policy:

- local/test-like environments may allow missing token when not configured
- strict environments require configured token
- weak tokens are rejected in strict mode
- token comparison uses constant-time `secrets.compare_digest`

## RSS Icon Read Safety

Icon path resolution enforces:

- non-empty paths only
- no absolute paths
- no parent-directory traversal
- final resolved file must stay inside the configured repository root
- only `.svg` files are served

## Qdrant Access

- optional API key support through `QDRANT_API_KEY`
- Qdrant failures are surfaced as upstream-style application errors
- no public Qdrant access is exposed directly by the service

## Browser-Related Middleware

- CORS is configurable through `CORS_ORIGINS`
- CSRF origin checks are applied only to unsafe `/api/*` routes
- the main exposed surface of this service is internal `/internal/*` routing

## Current Security Constraints

- inter-service auth still relies on a shared secret token
- environment misconfiguration can weaken route protection if local mode is
  incorrectly enabled
- the service has no dedicated readiness gate for Qdrant or Postgres yet
