"""Smoke tests: new Phase 4B ORM models are importable with correct table names."""


def test_new_models_importable() -> None:
    from calllens.db.models.agent_run import CallAgentRun
    from calllens.db.models.analysis import CallAnalysis
    from calllens.db.models.audit import AuditLog
    from calllens.db.models.coaching import CoachingNote

    assert CallAnalysis.__tablename__ == "call_analyses"
    assert CoachingNote.__tablename__ == "coaching_notes"
    assert AuditLog.__tablename__ == "audit_logs"
    assert CallAgentRun.__tablename__ == "call_agent_runs"
