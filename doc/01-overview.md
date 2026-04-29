# Overview

## Service Purpose

`content_service` is the internal read service for Manifeed content workflows.
It provides backend-only endpoints for source listings, source detail reads,
similar-source lookup, and RSS icon file reads.

This service is designed for trusted internal consumers and should not be
exposed directly to browsers or public clients.

## Responsibilities

- Expose source read models for admin-oriented use cases
- Expose source read models for user-oriented use cases
- Return detailed source payloads by ID
- Expose analysis overview for embedding coverage
- Query Qdrant for similar-source recommendations
- Serve RSS icon SVG files from the local RSS repository clone

## Technical Stack

- FastAPI
- SQLAlchemy + psycopg + PostgreSQL
- HTTPX for Qdrant communication
- Qdrant for vector similarity search
- Local repository-backed RSS icon reads
