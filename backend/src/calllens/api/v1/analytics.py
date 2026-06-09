"""Analytics API — read-only aggregation endpoints for the manager dashboard."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from calllens.core.deps import get_current_user
from calllens.core.scoring import AT_RISK_THRESHOLD, QUALITY_THRESHOLD
from calllens.core.scoring import band as band_from_score
from calllens.db.models.agent import Agent
from calllens.db.models.analysis import CallAnalysis
from calllens.db.models.call import Call, CallStatus
from calllens.db.models.team import Team
from calllens.db.models.topic import CallTopic, Topic
from calllens.db.models.user import User
from calllens.db.session import get_db
from calllens.schemas.analytics import (
    AnalyticsFilters,
    BandDistributionOut,
    ComplianceOut,
    ComplianceTrendPointOut,
    FlaggedCallOut,
    FlaggedListOut,
    LeaderboardEntryOut,
    LeaderboardOut,
    OverviewOut,
    QualityBucketOut,
    QualityTrendsOut,
    ScoreBucketOut,
    ScoreDistributionOut,
    TopicAnalyticsEntryOut,
    TopicAnalyticsOut,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_SCORED = Call.status == CallStatus.scored

_at_risk_clause = or_(
    CallAnalysis.escalate_for_review == True,  # noqa: E712
    CallAnalysis.overall_score < QUALITY_THRESHOLD,
)


def _apply_filters(
    stmt: Any,  # noqa: ANN401
    filters: AnalyticsFilters,
    *,
    agent_already_joined: bool = False,
) -> Any:  # noqa: ANN401
    """Append date / agent / team WHERE clauses to a SELECT statement.

    The statement must already include the calls table in its FROM clause.
    If team_id is set and agent_already_joined is False, an INNER JOIN to agents
    is added; calls with no agent are excluded when filtering by team (correct
    behaviour since they belong to no team).

    Args:
        stmt: A SQLAlchemy select statement.
        filters: Parsed query-param filter set.
        agent_already_joined: True when the query already JOINs the agents table.

    Returns:
        Statement with WHERE clauses (and optional join) appended.
    """
    if filters.date_from:
        stmt = stmt.where(Call.created_at >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Call.created_at <= filters.date_to)
    if filters.agent_id:
        stmt = stmt.where(Call.agent_id == filters.agent_id)
    if filters.team_id:
        if not agent_already_joined:
            stmt = stmt.join(Agent, Agent.id == Call.agent_id)
        stmt = stmt.where(Agent.team_id == filters.team_id)
    if filters.topic_id:
        stmt = stmt.join(CallTopic, CallTopic.call_id == Call.id).where(
            CallTopic.topic_id == filters.topic_id
        )
    return stmt


@router.get("/overview", response_model=OverviewOut)
async def get_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[AnalyticsFilters, Depends(AnalyticsFilters)],
) -> OverviewOut:
    """Return high-level call and score summary for the dashboard header.

    Args:
        db: Database session.
        current_user: Authenticated user.
        filters: Optional date / team / agent filters.

    Returns:
        OverviewOut with totals, averages, and rates.
    """
    stmt = (
        select(
            func.count(Call.id).label("calls_total"),
            func.count(CallAnalysis.id).label("calls_scored"),
            func.avg(CallAnalysis.overall_score).label("avg_score"),
            func.count(CallAnalysis.id)
            .filter(CallAnalysis.compliance_passed == True)  # noqa: E712
            .label("compliance_passed_count"),
            func.count(CallAnalysis.id).filter(_at_risk_clause).label("flagged_count"),
        )
        .select_from(Call)
        .outerjoin(CallAnalysis, CallAnalysis.call_id == Call.id)
    )
    stmt = _apply_filters(stmt, filters)
    row = (await db.execute(stmt)).one()
    calls_scored: int = row.calls_scored or 0
    avg: float | None = round(float(row.avg_score), 1) if row.avg_score is not None else None
    pass_rate: float | None = (
        round(row.compliance_passed_count / calls_scored, 4) if calls_scored > 0 else None
    )
    return OverviewOut(
        calls_total=row.calls_total,
        calls_scored=calls_scored,
        avg_overall_score=avg,
        compliance_pass_rate=pass_rate,
        flagged_count=row.flagged_count or 0,
    )


@router.get("/quality-trends", response_model=QualityTrendsOut)
async def get_quality_trends(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[AnalyticsFilters, Depends(AnalyticsFilters)],
    bucket: Annotated[str, Query(pattern="^(day|week)$")] = "day",
) -> QualityTrendsOut:
    """Return avg overall score and call count bucketed by day or week.

    Args:
        db: Database session.
        current_user: Authenticated user.
        filters: Optional date / team / agent filters.
        bucket: Bucket granularity — "day" or "week".

    Returns:
        QualityTrendsOut ordered chronologically.
    """
    bucket_col = func.date_trunc(bucket, Call.created_at).label("date_bucket")
    stmt = (
        select(
            bucket_col,
            func.avg(CallAnalysis.overall_score).label("avg_score"),
            func.count(CallAnalysis.id).label("calls_scored"),
        )
        .select_from(Call)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(_SCORED)
        .group_by(bucket_col)
        .order_by(bucket_col)
    )
    stmt = _apply_filters(stmt, filters)
    rows = (await db.execute(stmt)).all()
    return QualityTrendsOut(
        bucket=bucket,
        items=[
            QualityBucketOut(
                date=row.date_bucket.strftime("%Y-%m-%d"),
                avg_overall_score=round(float(row.avg_score), 1),
                calls_scored=row.calls_scored,
            )
            for row in rows
        ],
    )


@router.get("/score-distribution", response_model=ScoreDistributionOut)
async def get_score_distribution(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[AnalyticsFilters, Depends(AnalyticsFilters)],
) -> ScoreDistributionOut:
    """Return scored-call counts per 10-point bucket and per quality band.

    Args:
        db: Database session.
        current_user: Authenticated user.
        filters: Optional date / team / agent filters.

    Returns:
        ScoreDistributionOut with histogram buckets and band aggregates.
    """
    bucket_expr = cast(func.floor(CallAnalysis.overall_score / 10), Integer) * 10

    bucket_stmt = (
        select(bucket_expr.label("bucket"), func.count().label("cnt"))
        .select_from(Call)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(_SCORED)
        .group_by(bucket_expr)
        .order_by(bucket_expr)
    )
    bucket_stmt = _apply_filters(bucket_stmt, filters)

    band_stmt = (
        select(
            func.count().filter(CallAnalysis.overall_score >= QUALITY_THRESHOLD).label("quality"),
            func.count()
            .filter(
                (CallAnalysis.overall_score >= AT_RISK_THRESHOLD)
                & (CallAnalysis.overall_score < QUALITY_THRESHOLD)
            )
            .label("at_risk"),
            func.count().filter(CallAnalysis.overall_score < AT_RISK_THRESHOLD).label("fail"),
        )
        .select_from(Call)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(_SCORED)
    )
    band_stmt = _apply_filters(band_stmt, filters)

    bucket_rows = (await db.execute(bucket_stmt)).all()
    band_row = (await db.execute(band_stmt)).one()

    def _label(b: int) -> str:
        return f"{b}-{b + 9}" if b < 90 else "90-100"

    return ScoreDistributionOut(
        buckets=[
            ScoreBucketOut(bucket=row.bucket, label=_label(row.bucket), count=row.cnt)
            for row in bucket_rows
        ],
        bands=BandDistributionOut(
            quality=band_row.quality,
            at_risk=band_row.at_risk,
            fail=band_row.fail,
        ),
    )


@router.get("/compliance", response_model=ComplianceOut)
async def get_compliance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[AnalyticsFilters, Depends(AnalyticsFilters)],
) -> ComplianceOut:
    """Return overall compliance pass rate and weekly compliance trend.

    Args:
        db: Database session.
        current_user: Authenticated user.
        filters: Optional date / team / agent filters.

    Returns:
        ComplianceOut with overall pass_rate and weekly trend items.
    """
    week_col = func.date_trunc("week", Call.created_at).label("week_bucket")
    stmt = (
        select(
            week_col,
            func.count(CallAnalysis.id).label("calls"),
            func.count(CallAnalysis.id)
            .filter(CallAnalysis.compliance_passed == True)  # noqa: E712
            .label("passed"),
        )
        .select_from(Call)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(_SCORED)
        .group_by(week_col)
        .order_by(week_col)
    )
    stmt = _apply_filters(stmt, filters)
    rows = (await db.execute(stmt)).all()

    total_calls = sum(r.calls for r in rows)
    total_passed = sum(r.passed for r in rows)
    overall: float | None = round(total_passed / total_calls, 4) if total_calls > 0 else None
    return ComplianceOut(
        pass_rate=overall,
        trend=[
            ComplianceTrendPointOut(
                date=row.week_bucket.strftime("%Y-%m-%d"),
                pass_rate=round(row.passed / row.calls, 4) if row.calls > 0 else 0.0,
                calls=row.calls,
            )
            for row in rows
        ],
    )


@router.get("/flagged", response_model=FlaggedListOut)
async def get_flagged(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[AnalyticsFilters, Depends(AnalyticsFilters)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FlaggedListOut:
    """Return a paginated list of at-risk or escalated calls, newest first.

    Args:
        db: Database session.
        current_user: Authenticated user.
        filters: Optional date / team / agent filters.
        limit: Max results per page (1-200, default 50).
        offset: Pagination offset.

    Returns:
        FlaggedListOut sorted by upload date descending.
    """
    base = (
        select(
            Call.id,
            Agent.name.label("agent_name"),
            CallAnalysis.overall_score,
            CallAnalysis.escalate_for_review,
            CallAnalysis.escalation_reason,
            Call.created_at.label("uploaded_at"),
        )
        .select_from(Call)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .outerjoin(Agent, Agent.id == Call.agent_id)
        .where(_SCORED)
        .where(_at_risk_clause)
    )
    base = _apply_filters(base, filters, agent_already_joined=True)

    count_stmt = select(func.count()).select_from(base.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    rows = (
        await db.execute(base.order_by(Call.created_at.desc()).limit(limit).offset(offset))
    ).all()

    return FlaggedListOut(
        items=[
            FlaggedCallOut(
                call_id=row.id,
                agent_name=row.agent_name,
                overall_score=row.overall_score,
                band=band_from_score(row.overall_score),
                escalate_for_review=row.escalate_for_review,
                escalation_reason=row.escalation_reason,
                uploaded_at=row.uploaded_at,
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/leaderboard", response_model=LeaderboardOut)
async def get_leaderboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[AnalyticsFilters, Depends(AnalyticsFilters)],
) -> LeaderboardOut:
    """Return agents ranked by avg overall score among those with ≥1 scored call.

    Args:
        db: Database session.
        current_user: Authenticated user.
        filters: Optional date / team / agent filters.

    Returns:
        LeaderboardOut sorted by avg_overall_score descending.
    """
    avg_expr = func.avg(CallAnalysis.overall_score)
    stmt = (
        select(
            Agent.id,
            Agent.name,
            Team.name.label("team"),
            func.count(CallAnalysis.id).label("calls_scored"),
            avg_expr.label("avg_score"),
            func.count(CallAnalysis.id)
            .filter(CallAnalysis.compliance_passed == True)  # noqa: E712
            .label("compliance_passed_count"),
        )
        .select_from(Agent)
        .join(Team, Team.id == Agent.team_id)
        .join(Call, Call.agent_id == Agent.id)
        .join(CallAnalysis, CallAnalysis.call_id == Call.id)
        .where(_SCORED)
        .group_by(Agent.id, Agent.name, Team.id, Team.name)
        .having(func.count(CallAnalysis.id) >= 1)
        .order_by(avg_expr.desc())
    )
    # Leaderboard starts from Agent — apply filters directly
    if filters.date_from:
        stmt = stmt.where(Call.created_at >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Call.created_at <= filters.date_to)
    if filters.agent_id:
        stmt = stmt.where(Agent.id == filters.agent_id)
    if filters.team_id:
        stmt = stmt.where(Agent.team_id == filters.team_id)
    if filters.topic_id:
        stmt = stmt.join(CallTopic, CallTopic.call_id == Call.id).where(
            CallTopic.topic_id == filters.topic_id
        )

    rows = (await db.execute(stmt)).all()
    return LeaderboardOut(
        items=[
            LeaderboardEntryOut(
                agent_id=row.id,
                name=row.name,
                team=row.team,
                calls_scored=row.calls_scored,
                avg_overall_score=round(float(row.avg_score), 1),
                compliance_pass_rate=(
                    round(row.compliance_passed_count / row.calls_scored, 4)
                    if row.calls_scored > 0
                    else 0.0
                ),
                is_at_risk=round(float(row.avg_score), 1) < QUALITY_THRESHOLD,
            )
            for row in rows
        ]
    )


@router.get("/topics", response_model=TopicAnalyticsOut)
async def get_topic_analytics(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    filters: Annotated[AnalyticsFilters, Depends(AnalyticsFilters)],
) -> TopicAnalyticsOut:
    """Return per-topic call count, avg score, and flagged rate.

    Args:
        db: Database session.
        current_user: Authenticated user.
        filters: Optional date / team / agent / topic filters.

    Returns:
        TopicAnalyticsOut ordered by call_count desc.
    """
    stmt = (
        select(
            Topic.id,
            Topic.name,
            Topic.slug,
            func.count(Call.id.distinct()).label("call_count"),
            func.avg(CallAnalysis.overall_score).label("avg_score"),
            func.count(CallAnalysis.id.distinct()).filter(_at_risk_clause).label("flagged_count"),
            func.count(CallAnalysis.id.distinct()).label("scored_count"),
        )
        .select_from(Topic)
        .join(CallTopic, CallTopic.topic_id == Topic.id)
        .join(Call, Call.id == CallTopic.call_id)
        .outerjoin(CallAnalysis, CallAnalysis.call_id == Call.id)
        .group_by(Topic.id, Topic.name, Topic.slug)
        .order_by(func.count(Call.id.distinct()).desc())
    )

    # Apply date/agent/team filters on the Call table
    if filters.date_from:
        stmt = stmt.where(Call.created_at >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Call.created_at <= filters.date_to)
    if filters.agent_id:
        stmt = stmt.where(Call.agent_id == filters.agent_id)
    if filters.team_id:
        stmt = stmt.join(Agent, Agent.id == Call.agent_id).where(Agent.team_id == filters.team_id)

    rows = (await db.execute(stmt)).all()

    items: list[TopicAnalyticsEntryOut] = []
    for row in rows:
        avg = round(float(row.avg_score), 1) if row.avg_score is not None else None
        scored = row.scored_count or 0
        flagged_rate = round(row.flagged_count / scored, 4) if scored > 0 else None
        items.append(
            TopicAnalyticsEntryOut(
                topic_id=row.id,
                name=row.name,
                slug=row.slug,
                call_count=row.call_count,
                avg_overall_score=avg,
                band=band_from_score(int(avg)) if avg is not None else None,
                flagged_rate=flagged_rate,
            )
        )

    return TopicAnalyticsOut(items=items)
