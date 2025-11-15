# Yeirin AI - AI Recommendation Service

FastAPI-based RAG counseling center recommendation service

## Features

- OpenAI GPT-4o-mini based semantic analysis
- PostgreSQL read-only connection
- RAG (Retrieval-Augmented Generation) architecture

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Run server
uv run uvicorn yeirin_ai.main:app --reload --port 8001
```

## API Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/recommendations` - Get institution recommendations

## Tech Stack

- FastAPI 0.115+
- SQLAlchemy 2.0
- OpenAI 1.54+
- PostgreSQL 15
