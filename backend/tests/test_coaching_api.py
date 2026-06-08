"""HTTP tests for POST/GET/DELETE /coaching-notes."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _get_default_agent_id(client: AsyncClient, auth_token: str) -> str:
    resp = await client.get("/api/v1/agents", headers={"Authorization": f"Bearer {auth_token}"})
    return str(resp.json()["items"][0]["id"])


async def test_create_manual_coaching_note(client: AsyncClient, auth_token: str) -> None:
    agent_id = await _get_default_agent_id(client, auth_token)

    resp = await client.post(
        "/api/v1/coaching-notes",
        json={"agent_id": agent_id, "note": "Practice active listening."},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert body["source"] == "manual"
    assert body["note"] == "Practice active listening."
    assert body["call_id"] is None


async def test_list_coaching_notes_by_agent(client: AsyncClient, auth_token: str) -> None:
    agent_id = await _get_default_agent_id(client, auth_token)

    await client.post(
        "/api/v1/coaching-notes",
        json={"agent_id": agent_id, "note": "Note A."},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    resp = await client.get(
        f"/api/v1/coaching-notes?agent_id={agent_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert any(n["note"] == "Note A." for n in body["items"])


async def test_delete_manual_coaching_note(client: AsyncClient, auth_token: str) -> None:
    agent_id = await _get_default_agent_id(client, auth_token)

    create_resp = await client.post(
        "/api/v1/coaching-notes",
        json={"agent_id": agent_id, "note": "To be deleted."},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    note_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/coaching-notes/{note_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/api/v1/coaching-notes?agent_id={agent_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert all(n["id"] != note_id for n in list_resp.json()["items"])


async def test_delete_auto_note_rejected(
    client: AsyncClient, auth_token: str, db: AsyncSession
) -> None:
    """Trying to DELETE an auto-generated note must return 422."""
    from calllens.db.models.coaching import CoachingNote

    agent_id = await _get_default_agent_id(client, auth_token)

    note = CoachingNote(
        agent_id=uuid.UUID(agent_id),
        call_id=None,
        source="auto",
        note="Auto-generated.",
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    resp = await client.delete(
        f"/api/v1/coaching-notes/{note.id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 422


async def test_create_note_unknown_agent_returns_404(client: AsyncClient, auth_token: str) -> None:
    resp = await client.post(
        "/api/v1/coaching-notes",
        json={"agent_id": str(uuid.uuid4()), "note": "Note for nobody."},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 404
