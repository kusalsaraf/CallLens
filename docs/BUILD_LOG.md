# CallLens — Build Log

| Phase | Status | Commit | Date | Summary |
|-------|--------|--------|------|---------|
| 0 | done | `582d4b6` | 2026-06-07 | Monorepo layout, Python/FastAPI skeleton, docker-compose, CI workflow |
| 1A | done | `94bdec1` | 2026-06-07 | Single-user JWT auth: User model, Argon2 hashing, signup/login/refresh/logout/me |
| 1B | done | `3466905` | 2026-06-07 | Next.js frontend: marketing site, auth pages, protected app shell, 16 tests |
| 2A | done | `da913e8` | 2026-06-07 | Async processing spine: Team/Agent/Call/Transcript/Segment models, Alembic migration, local storage (aiofiles, Range streaming), stub transcriber + null diarizer (no heavy deps), Celery+Redis pipeline, 7 call API endpoints (upload, list, detail, transcript, audio, SSE, delete), 22 tests |
| 2B | done | TBD | 2026-06-07 | Upload page (drag-and-drop, XHR progress, SSE stepper), calls list (table, filters, pagination), call detail (audio player + two-way transcript sync via blob URL + fetch SSE) |
| 3A | done | `83c0a23` | 2026-06-07 | Scoring models (Rubric/CallScore/ScoreEvidence), LLM provider abstraction (stub+langchain), evidence validator, sentiment agent, scoring service + pipeline extension, scoring API (GET scores, POST reprocess), 23 tests |
| 3B | done | `41d822a` | 2026-06-08 | Evidence-linked scorecard: EvidenceChip, DimensionScoreCard, ScorecardPanel, two-column call-detail layout, focusedSegmentId wiring (audio seek + transcript highlight), score bands constants, scoring/scored status integration |
| 4A | done | TBD | 2026-06-08 | Multi-agent LangGraph scoring graph: TimedTranscriptSegmentData, ConversationMetrics (compute_metrics), FullRubricDimensionData, four specialist agents (sentiment, script, compliance, objection) + talk-listen ratio, supervisor node (weighted scoring, 3 escalation rules, LLM narrative), StateGraph fan-out with Send API, run_scoring_graph public API, 33 tests |
