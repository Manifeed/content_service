# Overview

## Service Purpose

`content_service` is the internal read service for Manifeed user-facing content
workflows. It provides backend-only endpoints for source listings, semantic
source search, source detail reads, and similar-source lookup.

This service is designed for trusted internal consumers and should not be
exposed directly to browsers or public clients.

## Responsibilities

- Expose source read models for user-oriented use cases
- Run semantic source search backed by embeddings and Qdrant
- Return detailed source payloads by ID
- Query Qdrant for similar-source recommendations

Admin-oriented source reads are handled by `admin_service`.

## Technical Stack

- FastAPI
- SQLAlchemy + psycopg + PostgreSQL
- HTTPX for embedding-service and Qdrant communication
- Qdrant for vector similarity search
