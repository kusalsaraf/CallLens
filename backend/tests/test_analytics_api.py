"""Tests for GET /api/v1/analytics/* endpoints."""

from __future__ import annotations

from httpx import AsyncClient

from calllens.core.scoring import QUALITY_THRESHOLD
from tests.conftest import AnalyticsDataset

# ── 401 guards ────────────────────────────────────────────────────────────────


async def test_overview_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/analytics/overview")).status_code == 401


async def test_quality_trends_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/analytics/quality-trends")).status_code == 401


async def test_score_distribution_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/analytics/score-distribution")).status_code == 401


async def test_compliance_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/analytics/compliance")).status_code == 401


async def test_flagged_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/analytics/flagged")).status_code == 401


async def test_leaderboard_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/analytics/leaderboard")).status_code == 401


# ── Overview ──────────────────────────────────────────────────────────────────


async def test_overview_totals(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/overview",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["calls_total"] == 8
    assert body["calls_scored"] == 6
    # avg = (80+90+55+40+75+30)/6 ≈ 61.7
    assert abs(body["avg_overall_score"] - 61.7) < 0.5
    # compliance_pass_rate = 4/6 ≈ 0.6667
    assert abs(body["compliance_pass_rate"] - 0.6667) < 0.001
    # flagged = score<80 OR escalate: c3(55), c4(40,esc), c5(75), c6(30,esc)
    assert body["flagged_count"] == 4


async def test_overview_agent_filter(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/overview",
        params={"agent_id": str(analytics_dataset.agent_a1_id)},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # A1: 2 scored + 1 unscored = 3 total, 2 scored, 0 flagged
    assert body["calls_scored"] == 2
    assert body["flagged_count"] == 0


async def test_overview_team_filter(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/overview",
        params={"team_id": str(analytics_dataset.team_beta_id)},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Beta: B1 scores 75 (<80, flagged) and 30 (escalate, flagged)
    assert body["calls_scored"] == 2
    assert body["flagged_count"] == 2


async def test_overview_date_filter(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/overview",
        params={"date_from": "2026-06-08T00:00:00Z", "date_to": "2026-06-08T23:59:59Z"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["calls_scored"] == 3  # c2, c4, c6 on june_8


# ── Quality trends ────────────────────────────────────────────────────────────


async def test_quality_trends_by_day(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/quality-trends",
        params={"bucket": "day"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucket"] == "day"
    items = body["items"]
    assert len(items) == 2
    # Items are ordered chronologically; first bucket = june_1 calls, second = june_8 calls.
    # Date strings are DB-timezone-dependent so we match by position, not string.
    june1 = items[0]
    assert abs(june1["avg_overall_score"] - 70.0) < 0.5  # (80+55+75)/3
    assert june1["calls_scored"] == 3
    june8 = items[1]
    assert abs(june8["avg_overall_score"] - 53.3) < 0.5  # (90+40+30)/3
    assert june8["calls_scored"] == 3


async def test_quality_trends_by_week(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/quality-trends",
        params={"bucket": "week"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucket"] == "week"
    items = body["items"]
    assert len(items) == 2
    assert sum(i["calls_scored"] for i in items) == 6


# ── Score distribution ────────────────────────────────────────────────────────


async def test_score_distribution_buckets(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/score-distribution",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    buckets = {b["bucket"]: b["count"] for b in body["buckets"]}
    assert buckets.get(30) == 1  # score=30
    assert buckets.get(40) == 1  # score=40
    assert buckets.get(50) == 1  # score=55
    assert buckets.get(70) == 1  # score=75
    assert buckets.get(80) == 1  # score=80
    assert buckets.get(90) == 1  # score=90
    assert sum(buckets.values()) == 6


async def test_score_distribution_bands(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/score-distribution",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    bands = body["bands"]
    # quality >=80: 80, 90; at-risk 60-79: 75; fail <60: 30, 40, 55
    assert bands["quality"] == 2
    assert bands["at_risk"] == 1  # 75
    assert bands["fail"] == 3  # 30, 40, 55
    assert bands["quality"] + bands["at_risk"] + bands["fail"] == 6


# ── Compliance ────────────────────────────────────────────────────────────────


async def test_compliance_overall_and_trend(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/compliance",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert abs(body["pass_rate"] - 0.6667) < 0.001  # 4/6
    assert len(body["trend"]) == 2
    # Trend is ordered chronologically; first week = june_1 calls (3/3 pass),
    # second week = june_8 calls (1/3 pass).
    # Date strings are DB-timezone-dependent so we match by position.
    june1_week = body["trend"][0]
    assert abs(june1_week["pass_rate"] - 1.0) < 0.001
    assert june1_week["calls"] == 3
    june8_week = body["trend"][1]
    assert abs(june8_week["pass_rate"] - 0.3333) < 0.001
    assert june8_week["calls"] == 3


# ── Flagged ───────────────────────────────────────────────────────────────────


async def test_flagged_returns_at_risk_calls(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/flagged",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # c3(55), c4(40,esc), c5(75), c6(30,esc) — 4 calls with band != quality
    assert body["total"] == 4
    assert len(body["items"]) == 4
    for item in body["items"]:
        assert item["escalate_for_review"] is True or item["overall_score"] < QUALITY_THRESHOLD


async def test_flagged_newest_first(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/flagged",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    dates = [item["uploaded_at"] for item in body["items"]]
    assert dates == sorted(dates, reverse=True)


async def test_flagged_pagination(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/flagged",
        params={"limit": 2, "offset": 0},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    assert body["total"] == 4
    assert len(body["items"]) == 2

    resp2 = await client.get(
        "/api/v1/analytics/flagged",
        params={"limit": 2, "offset": 2},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert len(resp2.json()["items"]) == 2


async def test_flagged_agent_filter(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/flagged",
        params={"agent_id": str(analytics_dataset.agent_a2_id)},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.json()["total"] == 2  # A2's two flagged calls (55, 40)


# ── Leaderboard ───────────────────────────────────────────────────────────────


async def test_leaderboard_order_and_is_at_risk(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/leaderboard",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    items = body["items"]
    # Default Agent from seed_defaults has 0 scored calls → excluded
    assert len(items) == 3
    avgs = [i["avg_overall_score"] for i in items]
    assert avgs == sorted(avgs, reverse=True)
    assert abs(items[0]["avg_overall_score"] - 85.0) < 0.5  # A1
    assert items[0]["is_at_risk"] is False
    assert items[-1]["is_at_risk"] is True


async def test_leaderboard_team_filter(
    client: AsyncClient, auth_token: str, analytics_dataset: AnalyticsDataset
) -> None:
    resp = await client.get(
        "/api/v1/analytics/leaderboard",
        params={"team_id": str(analytics_dataset.team_alpha_id)},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    body = resp.json()
    assert len(body["items"]) == 2  # A1, A2 only
    for item in body["items"]:
        assert item["team"] == "Alpha Team"
