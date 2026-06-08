"""Tests for GET /api/v1/teams/{id}/analytics."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from tests.conftest import AnalyticsDataset


async def test_team_analytics_requires_auth(client: AsyncClient) -> None:
    assert (await client.get(f"/api/v1/teams/{uuid.uuid4()}/analytics")).status_code == 401


async def test_team_analytics_404_on_missing(client: AsyncClient, auth_token: str) -> None:
    resp = await client.get(
        f"/api/v1/teams/{uuid.uuid4()}/analytics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 404


async def test_team_analytics_alpha_stats(
    client: AsyncClient,
    auth_token: str,
    analytics_dataset: AnalyticsDataset,
) -> None:
    resp = await client.get(
        f"/api/v1/teams/{analytics_dataset.team_alpha_id}/analytics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["calls_scored"] == 4
    assert abs(body["avg_overall_score"] - 66.25) < 0.5  # (80+90+55+40)/4
    assert abs(body["compliance_pass_rate"] - 0.75) < 0.01  # 3/4


async def test_team_analytics_alpha_bands(
    client: AsyncClient,
    auth_token: str,
    analytics_dataset: AnalyticsDataset,
) -> None:
    resp = await client.get(
        f"/api/v1/teams/{analytics_dataset.team_alpha_id}/analytics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    bands = body["score_distribution"]
    # quality >=80: 80, 90; at-risk 60-79: none; fail <60: 40, 55
    assert bands["quality"] == 2
    assert bands["at_risk"] == 0
    assert bands["fail"] == 2


async def test_team_analytics_agent_comparison(
    client: AsyncClient,
    auth_token: str,
    analytics_dataset: AnalyticsDataset,
) -> None:
    resp = await client.get(
        f"/api/v1/teams/{analytics_dataset.team_alpha_id}/analytics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    agents = body["agent_comparison"]
    assert len(agents) == 2  # A1, A2
    avgs = [a["avg_overall_score"] for a in agents]
    assert avgs == sorted(avgs, reverse=True)  # descending order
    assert abs(agents[0]["avg_overall_score"] - 85.0) < 0.5  # A1 first


async def test_team_analytics_beta_stats(
    client: AsyncClient,
    auth_token: str,
    analytics_dataset: AnalyticsDataset,
) -> None:
    resp = await client.get(
        f"/api/v1/teams/{analytics_dataset.team_beta_id}/analytics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["calls_scored"] == 2
    assert abs(body["avg_overall_score"] - 52.5) < 0.5
    assert abs(body["compliance_pass_rate"] - 0.5) < 0.01
