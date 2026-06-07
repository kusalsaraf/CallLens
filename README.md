# CallLens

AI-powered call-quality analytics platform. CallLens ingests recorded customer calls,
transcribes and analyses them with LLMs, surfaces quality scores, coaching insights, and
trend dashboards — giving revenue and support teams a clear lens into every conversation.

See [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for the full product and technical plan.

---

## Local setup

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `brew install uv`)
- Docker + Docker Compose

### 1. Start backing services

```bash
docker compose up -d
```

This starts Postgres 16 (with pgvector) on port 5432 and Redis 7 on port 6379.

### 2. Install dependencies

```bash
cd backend
uv sync --all-groups
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your local values if needed (defaults work with docker-compose)
```

### 4. Run database migrations

```bash
cd backend
uv run alembic upgrade head
```

### 5. Start the API server

```bash
cd backend
uv run uvicorn calllens.main:app --reload
```

The API is available at http://localhost:8000. Health check: http://localhost:8000/health

### 6. Run tests

```bash
cd backend
uv run pytest
```

### 7. Lint and type-check

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```
# CallLens
