# CallLens — Build Log

| Phase | Status | Commit | Date | Summary |
|-------|--------|--------|------|---------|
| 0 | done | `582d4b6` | 2026-06-07 | Monorepo layout, Python/FastAPI skeleton, docker-compose, CI workflow |
| 1A | done | `94bdec1` | 2026-06-07 | Single-user JWT auth: User model, Argon2 hashing, signup/login/refresh/logout/me |
| 1B | done | `3466905` | 2026-06-07 | Next.js frontend: marketing site, auth pages, protected app shell, 16 tests |
| 2A | done | `da913e8` | 2026-06-07 | Async processing spine: Team/Agent/Call/Transcript/Segment models, Alembic migration, local storage (aiofiles, Range streaming), stub transcriber + null diarizer (no heavy deps), Celery+Redis pipeline, 7 call API endpoints (upload, list, detail, transcript, audio, SSE, delete), 22 tests |
| 2B | done | TBD | 2026-06-07 | Upload page (drag-and-drop, XHR progress, SSE stepper), calls list (table, filters, pagination), call detail (audio player + two-way transcript sync via blob URL + fetch SSE) |
