# CallLens — Engineering Rules for Claude

These rules apply in every phase and every session. Follow them exactly.

## Git identity

Always use the project owner's identity for commits. Never add AI attribution:

```bash
git config user.name "Kusal Saraf"
git config user.email "kusalsaraf5@gmail.com"
```

- No "Co-Authored-By: Claude" trailers.
- No "Generated with Claude Code" footers.
- Commits must look authored solely by the project owner.

## Stack

| Concern | Choice |
|---------|--------|
| Language | Python 3.12 |
| Web framework | FastAPI (async) |
| ORM | async SQLAlchemy 2.0 |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Task queue | Celery + Redis |
| Dependency management | uv |
| Lint + format | ruff |
| Type checking | mypy |
| Testing | pytest + pytest-asyncio |

## Code style

- PEP 8, enforced by ruff.
- Full type hints on all functions and methods.
- Google-style docstrings on every public function and class.
- Small, single-responsibility functions — readable over clever.
- No comments explaining WHAT the code does; only WHY when non-obvious.

## Logging

- Structured JSON logging everywhere; **no `print()` statements**.
- Every request gets a correlation ID injected by middleware and propagated through logs.

## Error handling

- Custom exception hierarchy rooted at `AppError` (see `core/exceptions.py`).
- FastAPI exception handlers map exceptions to clean JSON HTTP responses.
- **Never leak stack traces or internal details to clients.**

## Configuration

- 12-factor config: all settings from environment variables via `pydantic-settings`.
- Secrets only via env vars; never hardcoded.
- `.env` is git-ignored; `.env.example` is committed with safe placeholder values.

## Database

- Async SQLAlchemy 2.0 engine + session factory.
- All schema changes through Alembic migrations — never `create_all()` in production code.

## Testing

- Tests ship in the **same slice** as the code they cover — no deferred test phases.
- Use `pytest-asyncio` for async tests; use `httpx.AsyncClient` for API tests.

## CI

- Every push and PR runs: `ruff check`, `ruff format --check`, `mypy`, `pytest`.
- CI must be green before merging.
