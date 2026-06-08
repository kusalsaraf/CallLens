"""HTTP tests for GET /agents, GET /agents/{id}, GET /agents/{id}/coaching."""

from __future__ import annotations

import uuid

from httpx import AsyncClient


async def test_list_agents_returns_items(client: AsyncClient, auth_token: str) -> None:
    resp = await client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    # seed_defaults creates one agent
    assert len(body["items"]) >= 1
    first = body["items"][0]
    assert "id" in first
    assert "name" in first
    assert "calls_scored" in first
    assert "avg_overall_score" in first


async def test_get_agent_by_id(client: AsyncClient, auth_token: str) -> None:
    list_resp = await client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    agent_id = list_resp.json()["items"][0]["id"]

    resp = await client.get(
        f"/api/v1/agents/{agent_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == agent_id
    assert body["calls_scored"] >= 0


async def test_get_agent_404(client: AsyncClient, auth_token: str) -> None:
    resp = await client.get(
        f"/api/v1/agents/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 404


async def test_get_agent_coaching_returns_list(client: AsyncClient, auth_token: str) -> None:
    list_resp = await client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    agent_id = list_resp.json()["items"][0]["id"]

    resp = await client.get(
        f"/api/v1/agents/{agent_id}/coaching",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["agent_id"] == agent_id
