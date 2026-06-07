# CallLens — Build Log

| Phase | Status | Commit | Date | Summary |
|-------|--------|--------|------|---------|
| 0 | done | `582d4b6` | 2026-06-07 | Monorepo layout, Python/FastAPI skeleton, docker-compose, CI workflow |
| 1A | done | `94bdec1` | 2026-06-07 | Single-user JWT auth: User model, Argon2 hashing, signup/login/refresh/logout/me |
| 1B | done | `3466905` | 2026-06-07 | Next.js frontend: marketing site, auth pages, protected app shell, 16 tests |
| 2A | done | TBD | 2026-06-07 | Async processing spine: Team/Agent/Call/Transcript/Segment models, Alembic migration, local storage (aiofiles, Range streaming), stub transcriber + null diarizer (no heavy deps), Celery+Redis pipeline, 7 call API endpoints (upload, list, detail, transcript, audio, SSE, delete), 22 tests |
