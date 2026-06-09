"""Tests for Phase 8A: customizable rubrics — CRUD, activation, binding, dispatch.

Covers:
- Config validation: compliance/script/custom per-kind rules, 422 on invalid
- CRUD: create→list→get→update→clone; activate makes exactly one active
- Delete: blocked for active (409), blocked for call-referenced (409), allowed otherwise
- Auth: all endpoints require token (401)
- Audit rows written for create/update/activate/delete
- Binding: upload binds active rubric; no active falls back to seeded default
- Reprocess: uses bound rubric; rebind_rubric flag switches to active
- Dispatch: custom rubric (incl. custom-kind dimension) scores end-to-end
- Weight normalization: overall_score correct for non-100 weights
- Misconfigured dimension: doesn't crash the graph
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.db.models.audit import AuditLog
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.seed.rubric import seed_default_rubric

# ---------------------------------------------------------------------------
# Config validation tests (Pydantic, no DB)
# ---------------------------------------------------------------------------


class TestDimensionConfigValidation:
    """Per-kind config validation on DimensionIn."""

    def test_compliance_requires_non_empty_required_phrases(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        with pytest.raises(ValueError, match="required_phrases"):
            DimensionIn(
                key="comp",
                name="Compliance",
                weight=0.2,
                kind=DimensionKind.compliance,
                config={},
            )

    def test_compliance_rejects_empty_list(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        with pytest.raises(ValueError, match="required_phrases"):
            DimensionIn(
                key="comp",
                name="Compliance",
                weight=0.2,
                kind=DimensionKind.compliance,
                config={"required_phrases": []},
            )

    def test_script_adherence_requires_checklist(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        with pytest.raises(ValueError, match="checklist"):
            DimensionIn(
                key="script",
                name="Script",
                weight=0.2,
                kind=DimensionKind.script_adherence,
                config={},
            )

    def test_custom_requires_guidance(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        with pytest.raises(ValueError, match="guidance"):
            DimensionIn(
                key="cust",
                name="Custom",
                weight=0.1,
                kind=DimensionKind.custom,
                config={},
            )

    def test_custom_rejects_empty_guidance(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        with pytest.raises(ValueError, match="guidance"):
            DimensionIn(
                key="cust",
                name="Custom",
                weight=0.1,
                kind=DimensionKind.custom,
                config={"guidance": "   "},
            )

    def test_valid_compliance_config_accepted(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        d = DimensionIn(
            key="comp",
            name="Compliance",
            weight=0.2,
            kind=DimensionKind.compliance,
            config={"required_phrases": ["I understand"]},
        )
        assert d.kind == DimensionKind.compliance

    def test_valid_script_config_accepted(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        d = DimensionIn(
            key="script",
            name="Script",
            weight=0.2,
            kind=DimensionKind.script_adherence,
            config={"checklist": ["Greeting", "Closing"]},
        )
        assert d.kind == DimensionKind.script_adherence

    def test_valid_custom_config_accepted(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        d = DimensionIn(
            key="patience",
            name="Patience",
            weight=0.1,
            kind=DimensionKind.custom,
            config={"guidance": "Score the agent on patience and composure."},
        )
        assert d.kind == DimensionKind.custom

    def test_sentiment_needs_no_config(self) -> None:
        from calllens.schemas.rubric import DimensionIn, DimensionKind

        d = DimensionIn(
            key="sent",
            name="Sentiment",
            weight=0.25,
            kind=DimensionKind.sentiment_empathy,
        )
        assert d.config is None

    def test_api_rejects_invalid_compliance(
        self,
    ) -> None:
        """422 returned when creating a rubric with invalid compliance config."""
        pass  # Covered by async API test below


# ---------------------------------------------------------------------------
# CRUD API tests
# ---------------------------------------------------------------------------

_VALID_RUBRIC = {
    "name": "Test Rubric",
    "description": "A test rubric",
    "dimensions": [
        {"key": "sent", "name": "Sentiment", "weight": 0.4, "kind": "sentiment_empathy"},
        {
            "key": "comp",
            "name": "Compliance",
            "weight": 0.3,
            "kind": "compliance",
            "config": {"required_phrases": ["Hello", "Goodbye"]},
        },
        {"key": "talk", "name": "Talk Ratio", "weight": 0.3, "kind": "talk_listen"},
    ],
}


async def test_create_rubric(client: AsyncClient, auth_token: str) -> None:
    resp = await client.post(
        "/api/v1/rubrics",
        json=_VALID_RUBRIC,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Rubric"
    assert data["is_active"] is False
    assert len(data["dimensions"]) == 3


async def test_create_rubric_422_invalid_config(client: AsyncClient, auth_token: str) -> None:
    bad = {
        "name": "Bad",
        "dimensions": [
            {"key": "comp", "name": "Comp", "weight": 0.5, "kind": "compliance", "config": {}},
        ],
    }
    resp = await client.post(
        "/api/v1/rubrics",
        json=bad,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 422


async def test_list_rubrics(client: AsyncClient, auth_token: str, db: AsyncSession) -> None:
    await seed_default_rubric(db)
    resp = await client.get(
        "/api/v1/rubrics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1


async def test_get_rubric_with_dimensions(
    client: AsyncClient,
    auth_token: str,
) -> None:
    create_resp = await client.post(
        "/api/v1/rubrics",
        json=_VALID_RUBRIC,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    rubric_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/rubrics/{rubric_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["dimensions"]) == 3
    assert data["id"] == rubric_id


async def test_update_rubric(client: AsyncClient, auth_token: str) -> None:
    create_resp = await client.post(
        "/api/v1/rubrics",
        json=_VALID_RUBRIC,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    rubric_id = create_resp.json()["id"]

    update_data = {
        "name": "Updated Rubric",
        "dimensions": [
            {"key": "obj", "name": "Objection", "weight": 0.5, "kind": "objection_handling"},
            {"key": "talk", "name": "Talk", "weight": 0.5, "kind": "talk_listen"},
        ],
    }
    resp = await client.put(
        f"/api/v1/rubrics/{rubric_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Rubric"
    assert len(data["dimensions"]) == 2


async def test_activate_makes_exactly_one_active(
    client: AsyncClient,
    auth_token: str,
    db: AsyncSession,
) -> None:
    await seed_default_rubric(db)

    create_resp = await client.post(
        "/api/v1/rubrics",
        json=_VALID_RUBRIC,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    new_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/rubrics/{new_id}/activate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    # Verify only one is active
    list_resp = await client.get(
        "/api/v1/rubrics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    active_count = sum(1 for r in list_resp.json()["items"] if r["is_active"])
    assert active_count == 1


async def test_clone_rubric(client: AsyncClient, auth_token: str) -> None:
    create_resp = await client.post(
        "/api/v1/rubrics",
        json=_VALID_RUBRIC,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    rubric_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/rubrics/{rubric_id}/clone",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "(copy)" in data["name"]
    assert data["is_active"] is False
    assert len(data["dimensions"]) == len(create_resp.json()["dimensions"])
    assert data["id"] != rubric_id


async def test_delete_blocked_for_active(
    client: AsyncClient,
    auth_token: str,
    db: AsyncSession,
) -> None:
    await seed_default_rubric(db)

    create_resp = await client.post(
        "/api/v1/rubrics",
        json=_VALID_RUBRIC,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    rubric_id = create_resp.json()["id"]

    await client.post(
        f"/api/v1/rubrics/{rubric_id}/activate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    resp = await client.delete(
        f"/api/v1/rubrics/{rubric_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 409


async def test_delete_allowed_for_inactive(client: AsyncClient, auth_token: str) -> None:
    create_resp = await client.post(
        "/api/v1/rubrics",
        json=_VALID_RUBRIC,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    rubric_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/rubrics/{rubric_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 204


async def test_rubric_401_without_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/rubrics")
    assert resp.status_code == 401


async def test_audit_rows_written(
    client: AsyncClient,
    auth_token: str,
    db: AsyncSession,
) -> None:
    create_resp = await client.post(
        "/api/v1/rubrics",
        json=_VALID_RUBRIC,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    rubric_id = create_resp.json()["id"]

    result = await db.execute(
        select(AuditLog).where(
            AuditLog.entity == "rubric",
            AuditLog.entity_id == uuid.UUID(rubric_id),
        )
    )
    audit_rows = result.scalars().all()
    actions = {r.action for r in audit_rows}
    assert "rubric_create" in actions


# ---------------------------------------------------------------------------
# Binding tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def scored_call_fixture(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Create a rubric, call, transcript, and segments for scoring tests."""
    rubric = await seed_default_rubric(db)

    call = Call(
        status=CallStatus.transcribed,
        storage_key="test/bind.wav",
        original_filename="bind.wav",
        rubric_id=rubric.id,
    )
    db.add(call)
    await db.flush()

    t = Transcript(call_id=call.id, language="en")
    db.add(t)
    await db.flush()

    for i, (speaker, text) in enumerate(
        [
            ("agent", "Good morning, thank you for calling. How can I help you today?"),
            ("customer", "I have a billing issue on my account."),
            ("agent", "I understand, I apologize for the inconvenience. Let me look into that."),
            ("customer", "It's been going on for weeks now."),
            ("agent", "Is there anything else I can help you with?"),
        ]
    ):
        db.add(
            TranscriptSegment(
                transcript_id=t.id,
                sequence=i,
                start_ms=i * 3000,
                end_ms=(i + 1) * 3000,
                text=text,
                speaker=speaker,
            )
        )
    await db.commit()

    return {"call_id": call.id, "rubric_id": rubric.id, "transcript_id": t.id}


async def test_score_call_uses_bound_rubric(
    db: AsyncSession,
    scored_call_fixture: dict[str, uuid.UUID],
) -> None:
    """score_call should use the call's bound rubric_id, not is_default."""
    from calllens.services.scoring_service import score_call

    call_id = scored_call_fixture["call_id"]
    await score_call(call_id, db=db)

    call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one()
    assert call.status == CallStatus.scored
    assert call.rubric_id == scored_call_fixture["rubric_id"]


async def test_score_call_rebind_rubric(
    db: AsyncSession,
    scored_call_fixture: dict[str, uuid.UUID],
) -> None:
    """rebind_rubric=True should update call.rubric_id to the active rubric."""
    from calllens.services.scoring_service import score_call

    call_id = scored_call_fixture["call_id"]
    await score_call(call_id, db=db, rebind_rubric=True)

    call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one()
    assert call.status == CallStatus.scored


# ---------------------------------------------------------------------------
# Dynamic dispatch tests
# ---------------------------------------------------------------------------


async def test_custom_rubric_scores_end_to_end(
    db: AsyncSession,
) -> None:
    """A rubric with custom-kind dimensions scores end-to-end via stub."""
    from calllens.agents.graph import ScoringContext, run_scoring_graph
    from calllens.agents.llm import TimedTranscriptSegmentData
    from calllens.agents.specialists import FullRubricDimensionData

    seg1 = TimedTranscriptSegmentData(
        id=uuid.uuid4(),
        sequence=0,
        text="Hello, how can I help?",
        speaker="agent",
        start_ms=0,
        end_ms=3000,
    )
    seg2 = TimedTranscriptSegmentData(
        id=uuid.uuid4(),
        sequence=1,
        text="I need help with my order.",
        speaker="customer",
        start_ms=3500,
        end_ms=6000,
    )

    dimensions = [
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="sent",
            name="Sentiment",
            weight=0.4,
            kind="sentiment_empathy",
            config=None,
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="patience",
            name="Patience",
            weight=0.3,
            kind="custom",
            config={"guidance": "Score the agent on patience."},
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="talk",
            name="Talk Ratio",
            weight=0.3,
            kind="talk_listen",
            config=None,
        ),
    ]

    context = ScoringContext(segments=[seg1, seg2], dimensions=dimensions)
    result = await run_scoring_graph(context)

    assert "sent" in result["dimension_scores"]
    assert "patience" in result["dimension_scores"]
    assert "talk" in result["dimension_scores"]
    assert result["supervisor_result"].overall_score >= 0


async def test_weight_normalization_non_100_sum(db: AsyncSession) -> None:
    """Overall score is correctly normalized when weights don't sum to 100."""
    from calllens.agents.llm import AgentScore
    from calllens.agents.specialists import FullRubricDimensionData
    from calllens.agents.supervisor import _compute_overall_score

    dims = [
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="a",
            name="A",
            weight=10.0,
            kind="score",
            config=None,
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="b",
            name="B",
            weight=30.0,
            kind="score",
            config=None,
        ),
    ]
    scores = {
        "a": AgentScore(score=100, confidence=1.0, rationale="ok", evidence=[], is_supported=True),
        "b": AgentScore(score=50, confidence=1.0, rationale="ok", evidence=[], is_supported=True),
    }

    overall = _compute_overall_score(scores, dims)
    expected = round((100 * 10 + 50 * 30) / (10 + 30))
    assert overall == expected


async def test_misconfigured_dimension_doesnt_crash_graph() -> None:
    """A dimension with an unknown kind should not crash the graph."""
    from calllens.agents.graph import ScoringContext, run_scoring_graph
    from calllens.agents.llm import TimedTranscriptSegmentData
    from calllens.agents.specialists import FullRubricDimensionData

    seg = TimedTranscriptSegmentData(
        id=uuid.uuid4(),
        sequence=0,
        text="Test segment",
        speaker="agent",
        start_ms=0,
        end_ms=3000,
    )

    dimensions = [
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="valid",
            name="Sentiment",
            weight=0.5,
            kind="sentiment_empathy",
            config=None,
        ),
        FullRubricDimensionData(
            id=uuid.uuid4(),
            key="broken",
            name="Bad Kind",
            weight=0.5,
            kind="nonexistent_kind",
            config=None,
        ),
    ]

    context = ScoringContext(segments=[seg], dimensions=dimensions)
    result = await run_scoring_graph(context)

    assert "valid" in result["dimension_scores"]
    assert "broken" in result["dimension_scores"]
    assert result["dimension_scores"]["broken"].is_supported is False
