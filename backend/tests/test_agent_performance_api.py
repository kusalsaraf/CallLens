"""Tests for GET /api/v1/agents/{id}/performance."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from tests.conftest import AnalyticsDataset


async def test_agent_performance_requires_auth(client: AsyncClient) -> None:
    assert (await client.get(f"/api/v1/agents/{uuid.uuid4()}/performance")).status_code == 401


async def test_agent_performance_404_on_missing(client: AsyncClient, auth_token: str) -> None:
    resp = await client.get(
        f"/api/v1/agents/{uuid.uuid4()}/performance",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 404


async def test_agent_performance_basic_stats(
    client: AsyncClient,
    auth_token: str,
    analytics_dataset: AnalyticsDataset,
) -> None:
    resp = await client.get(
        f"/api/v1/agents/{analytics_dataset.agent_a1_id}/performance",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["calls_scored"] == 2
    assert abs(body["avg_overall_score"] - 85.0) < 0.5  # (80+90)/2


async def test_agent_performance_weekly_trend(
    client: AsyncClient,
    auth_token: str,
    analytics_dataset: AnalyticsDataset,
) -> None:
    resp = await client.get(
        f"/api/v1/agents/{analytics_dataset.agent_a1_id}/performance",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    trend = body["trend"]
    assert len(trend) == 2
    # Items ordered chronologically; use positional matching (timezone-independent)
    assert abs(trend[0]["avg_overall_score"] - 80.0) < 0.5  # june_1 call score=80
    assert abs(trend[1]["avg_overall_score"] - 90.0) < 0.5  # june_8 call score=90


async def test_agent_performance_vs_team(
    client: AsyncClient,
    auth_token: str,
    analytics_dataset: AnalyticsDataset,
) -> None:
    resp = await client.get(
        f"/api/v1/agents/{analytics_dataset.agent_a1_id}/performance",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    vs = body["vs_team"]
    assert abs(vs["agent_avg"] - 85.0) < 0.5  # A1 avg
    assert abs(vs["team_avg"] - 66.25) < 0.5  # Alpha avg (80+90+55+40)/4


async def test_agent_performance_dimension_breakdown_is_list(
    client: AsyncClient,
    auth_token: str,
    analytics_dataset: AnalyticsDataset,
) -> None:
    resp = await client.get(
        f"/api/v1/agents/{analytics_dataset.agent_a1_id}/performance",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    # No CallScore rows in fixture → empty list is correct, not an error
    assert isinstance(body["dimension_breakdown"], list)
