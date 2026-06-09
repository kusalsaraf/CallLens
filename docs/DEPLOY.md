# CallLens — Deployment Guide

## Quick Start (Docker Compose)

Run the entire stack locally with one command — no API keys needed:

```bash
cp .env.example .env
docker compose up --build
```

- **App:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **Dashboard:** pre-seeded with 16 demo calls (`SEED_DEMO_ON_START=true`)

### Infra-only (for native dev with `uv` + `npm`)

Run only Postgres and Redis in Docker, then start the backend and frontend natively:

```bash
docker compose up postgres redis
```

Then in separate terminals:

```bash
# Backend
cd backend && cp .env.example .env   # edit DATABASE_URL to localhost
uv sync --group agents
uv run alembic upgrade head
uv run uvicorn calllens.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

### Reset everything (including data)

```bash
docker compose down -v
```

This removes all containers and named volumes (`pgdata`, `storage`).

### How the services fit together

| Service | Image | Purpose |
|---------|-------|---------|
| `postgres` | pgvector/pgvector:pg16 | Database with vector extension |
| `redis` | redis:7-alpine | Celery broker + result backend |
| `migrate` | backend Dockerfile | Runs `alembic upgrade head` once, then exits |
| `api` | backend Dockerfile | FastAPI server (uvicorn) |
| `worker` | backend Dockerfile | Celery background worker |
| `frontend` | frontend Dockerfile | Next.js standalone server |

The `api` and `worker` services **share a Docker volume** (`storage`) mounted
at `/data/storage`. This is critical — the worker must read audio files that
the API wrote during upload.

---

## Architecture

```
┌─────────────────┐      /api/*       ┌────────────────────────────────┐
│  Vercel (Next.js)│ ──── rewrite ───→ │  Render (FastAPI + Celery)     │
│  frontend        │                   │  honcho start (combined mode)  │
└─────────────────┘                   └────────┬───────────────────────┘
                                               │
                                    ┌──────────┼──────────┐
                                    ▼          ▼          ▼
                               Supabase    Upstash    (optional)
                               Postgres    Redis      S3/R2
```

The frontend talks to `/api/*` on the same origin; Next.js rewrites those
requests to `BACKEND_URL`. This keeps the httpOnly refresh cookie first-party
(SameSite=Lax works without SameSite=None).

## Run Modes

| Mode | Command | Use case |
|------|---------|----------|
| **Docker Compose** | `docker compose up --build` | Full stack locally |
| **Combined** | `honcho start` | Free tier — runs API + Celery worker in one process |
| **API only** | `uvicorn calllens.main:app ...` | Paid tier — dedicated web service |
| **Worker only** | `celery -A calllens.tasks.celery_app:celery_app worker ...` | Paid tier — dedicated background worker |
| **Migrate** | `alembic upgrade head` | One-off pre-deploy command |
| **Seed** | `python -m calllens.seed.demo --count 16` | Populate demo data |

## Provider Settings — Free vs Paid Instance

The free Render tier gives 512 MB RAM and a single instance. Provider choices
must fit within that budget.

| Provider setting | Free-tier safe | Needs paid instance | Notes |
|------------------|:-:|:-:|-------|
| `TRANSCRIBER_PROVIDER=stub` | Yes | — | No audio processing |
| `TRANSCRIBER_PROVIDER=assemblyai` | Yes | — | API-offloaded (HTTP call to AssemblyAI) |
| `TRANSCRIBER_PROVIDER=faster_whisper` | — | Yes | Loads Whisper model into RAM (~500 MB+) |
| `LLM_PROVIDER=stub` | Yes | — | Deterministic scoring, no API key needed |
| `LLM_PROVIDER=langchain` | Yes | — | API-offloaded (HTTP calls to Gemini/Groq) |
| `EMBEDDING_PROVIDER=stub` | Yes | — | Fixed-vector embeddings, no model loaded |
| `EMBEDDING_PROVIDER=local` | — | Yes | Loads sentence-transformers model (~300 MB) |
| `EMBEDDING_PROVIDER=gemini` | Yes | — | API-offloaded to Google |
| `REDACTION_PROVIDER=regex` | Yes | — | Zero-dependency regex patterns |
| `REDACTION_PROVIDER=presidio` | — | Yes | Loads spaCy NER model (~200 MB) |
| `TOPIC_EXTRACTOR=stub` | Yes | — | Keyword-based, no model |
| `TOPIC_EXTRACTOR=llm` | Yes | — | API-offloaded via LLM provider |
| `STORAGE_BACKEND=local` | Yes | — | Ephemeral on free tier (disk resets on deploy) |
| `STORAGE_BACKEND=s3` | Yes | — | Persistent; needs S3/R2 credentials |

**Recommendation for free tier:** `stub` or API-offloaded providers only.
Switch to `local` embedding or `presidio` redaction only on a paid instance
with >=1 GB RAM.

## Render Blueprint

The repo includes a `render.yaml` at the root. To deploy:

1. Push the repo to GitHub.
2. In the Render dashboard, create a **Blueprint Instance** pointing at the repo.
3. Render reads `render.yaml` and provisions the web service.
4. Set the secrets in the dashboard: `DATABASE_URL`, `REDIS_URL`,
   and any API keys you want to enable.
5. Update `CORS_ORIGINS` to your actual Vercel frontend URL.

The blueprint uses `honcho start` (combined API + worker) for the free tier.
To split into dedicated services, uncomment the worker block in `render.yaml`
and switch the web service back to the default `uvicorn` command.

## Required External Services

| Service | Free-tier option | Purpose |
|---------|-----------------|---------|
| **PostgreSQL** | Supabase free tier | Primary database (use port 6543 + `DB_USE_PGBOUNCER=true`) |
| **Redis** | Upstash free tier | Celery broker + result backend |
| **S3 storage** | Cloudflare R2 (10 GB free) | Audio file storage (optional — `local` works for demo) |

## Environment Variables

- **Docker Compose:** see `.env.example` at the repo root
- **Backend (native):** see `backend/.env.example`
- **Frontend (Vercel):** see `frontend/.env.production.example`
