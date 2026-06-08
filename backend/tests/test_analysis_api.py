"""HTTP tests for GET /analysis, GET /trace, GET /scores band."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import calllens.db.models  # noqa: F401
from calllens.db.models.agent import Agent
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.seed.rubric import seed_default_rubric
from calllens.services.scoring_service import score_call
from calllens.services.seed import seed_defaults


async def _make_scored_call(db: AsyncSession) -> uuid.UUID:
    """Seed a transcribed call, score it, return call_id."""
    await seed_defaults(db)
    await seed_default_rubric(db)
    agent = (await db.execute(select(Agent).limit(1))).scalar_one()
    call = Call(
        id=uuid.uuid4(),
        status=CallStatus.transcribed,
        storage_key="test.wav",
        original_filename="test.wav",
        agent_id=agent.id,
    )
    db.add(call)
    await db.flush()
    transcript = Transcript(id=uuid.uuid4(), call_id=call.id, language="en")
    db.add(transcript)
    await db.flush()
    for i in range(4):
        db.add(
            TranscriptSegment(
                id=uuid.uuid4(),
                transcript_id=transcript.id,
                sequence=i,
                start_ms=i * 3000,
                end_ms=(i + 1) * 3000,
                text=f"Segment {i}.",
                speaker="agent" if i % 2 == 0 else "customer",
            )
        )
    await db.commit()
    call_id = call.id
    await score_call(call_id, db=db)
    return call_id


async def test_get_analysis_404_before_scoring(
    client: AsyncClient, auth_token: str, db: AsyncSession
) -> None:
    """GET /analysis returns 404 when no analysis exists for the call."""
    await seed_defaults(db)
    await seed_default_rubric(db)
    agent = (await db.execute(select(Agent).limit(1))).scalar_one()
    call = Call(
        id=uuid.uuid4(),
        status=CallStatus.uploaded,
        storage_key="unscored.wav",
        original_filename="unscored.wav",
        agent_id=agent.id,
    )
    db.add(call)
    await db.commit()

    resp = await client.get(
        f"/api/v1/calls/{call.id}/analysis",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 404


async def test_get_analysis_returns_data_after_scoring(
    client: AsyncClient, auth_token: str, db: AsyncSession
) -> None:
    """GET /analysis returns 200 with analysis data after scoring."""
    call_id = await _make_scored_call(db)

    resp = await client.get(
        f"/api/v1/calls/{call_id}/analysis",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["call_id"] == str(call_id)
    assert 0 <= body["overall_score"] <= 100
    assert len(body["summary"]) > 0
    assert isinstance(body["action_items"], list)
    assert isinstance(body["compliance_passed"], bool)


async def test_get_scores_includes_band(
    client: AsyncClient, auth_token: str, db: AsyncSession
) -> None:
    """A scored call's /scores response includes a band field on each score."""
    call_id = await _make_scored_call(db)

    resp = await client.get(
        f"/api/v1/calls/{call_id}/scores",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["scores"]) > 0
    for score in body["scores"]:
        assert "band" in score
        assert score["band"] in ("quality", "at-risk", "fail")


async def test_get_trace_returns_runs(
    client: AsyncClient, auth_token: str, db: AsyncSession
) -> None:
    """GET /trace returns runs with at least preprocess + supervisor nodes."""
    call_id = await _make_scored_call(db)

    resp = await client.get(
        f"/api/v1/calls/{call_id}/trace",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["call_id"] == str(call_id)
    nodes = [r["node"] for r in body["runs"]]
    assert "preprocess" in nodes
    assert "supervisor" in nodes
