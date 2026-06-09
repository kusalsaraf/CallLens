# ── Stage 1: builder ─────────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Install base deps only (no heavy optional groups like transcription-local, agents, etc.)
RUN uv sync --no-dev --frozen

# ── Stage 2: runtime ────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN groupadd --gid 1001 calllens && \
    useradd --uid 1001 --gid calllens --shell /bin/false calllens

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER calllens

EXPOSE 8000

# Default: run the API server. Override CMD for worker mode.
# WEB_CONCURRENCY controls the number of uvicorn workers (default 2).
#
# Run modes:
#   API:      docker run <image>  (default, runs uvicorn)
#   Worker:   docker run <image> celery -A calllens.worker worker --loglevel=info
#   Migrate:  docker run <image> alembic upgrade head
#   Seed:     docker run <image> python -m calllens.seed.demo --count 16

CMD ["uvicorn", "calllens.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
