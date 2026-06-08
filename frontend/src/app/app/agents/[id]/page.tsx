"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { cn } from "@/lib/utils";
import { CardSkeleton } from "@/components/overview/CardSkeleton";
import { DimensionBreakdown } from "@/components/agents/DimensionBreakdown";
import { VsTeamCard } from "@/components/agents/VsTeamCard";
import { CoachingPanel } from "@/components/agents/CoachingPanel";
import {
  scoreBand,
  BAND_TEXT_CLASS,
  BAND_BG_CLASS,
} from "@/lib/constants/scoreBands";
import {
  apiGetAgent,
  apiGetAgentPerformance,
  apiGetAgentCoaching,
} from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";

const QUALITY_LINE = 80;
const AT_RISK_LINE = 60;

function AgentDetailContent() {
  const { id } = useParams<{ id: string }>();

  const {
    data: agent,
    isLoading: loadingAgent,
    error: agentError,
  } = useQuery({
    queryKey: ["agent", id],
    queryFn: () => apiGetAgent(id),
    retry: (count, err) => {
      if (err instanceof ApiError && err.status === 404) return false;
      return count < 2;
    },
  });

  const { data: performance, isLoading: loadingPerf } = useQuery({
    queryKey: ["agent-performance", id],
    queryFn: () => apiGetAgentPerformance(id),
    enabled: !!agent,
    retry: false,
  });

  const { data: coaching, isLoading: loadingCoaching } = useQuery({
    queryKey: ["agent-coaching", id],
    queryFn: () => apiGetAgentCoaching(id),
    enabled: !!agent,
  });

  // 404 state
  if (
    agentError instanceof ApiError &&
    agentError.status === 404
  ) {
    return (
      <div
        data-testid="agent-not-found"
        className="flex flex-col items-center justify-center gap-4 p-16 text-center"
      >
        <span className="text-4xl">🔍</span>
        <h2 className="text-lg font-semibold text-foreground">Agent not found</h2>
        <p className="text-sm text-muted-foreground">
          This agent doesn&apos;t exist or has been removed.
        </p>
        <Link
          href="/app/agents"
          className="text-sm text-primary underline-offset-2 hover:underline"
        >
          ← Back to Agents
        </Link>
      </div>
    );
  }

  const band = agent ? scoreBand(agent.avg_overall_score) : null;

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Back */}
      <Link
        href="/app/agents"
        className="self-start text-sm text-muted-foreground hover:text-foreground"
      >
        ← Agents
      </Link>

      {/* Header */}
      {loadingAgent ? (
        <CardSkeleton height="h-24" data-testid="card-skeleton" />
      ) : agent ? (
        <div
          data-testid="agent-header"
          className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-card p-5 shadow-sm"
        >
          <div className="flex-1 min-w-0">
            <h1
              data-testid="agent-name"
              className="text-xl font-bold text-foreground truncate"
            >
              {agent.name}
            </h1>
            <p className="text-sm text-muted-foreground">Agent ID: {agent.id}</p>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <p className="text-xs text-muted-foreground">Calls Scored</p>
              <p className="tabular text-xl font-bold text-foreground">
                {agent.calls_scored}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-muted-foreground">Avg Score</p>
              <p
                data-testid="agent-avg-score"
                className={cn("tabular text-xl font-bold", band ? BAND_TEXT_CLASS[band] : "")}
              >
                {agent.avg_overall_score}
              </p>
            </div>
            {band && band !== "quality" && (
              <span
                data-testid="agent-at-risk"
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium",
                  BAND_BG_CLASS[band],
                  BAND_TEXT_CLASS[band],
                )}
              >
                {band === "at-risk" ? "At-risk" : "Fail"}
              </span>
            )}
          </div>
        </div>
      ) : null}

      {/* Quality trend */}
      <div
        data-testid="agent-trend-card"
        className="rounded-lg border border-border bg-card p-5 shadow-sm"
      >
        <h3 className="mb-3 text-sm font-semibold text-foreground">
          Quality Trend (weekly)
        </h3>
        {loadingPerf ? (
          <div className="h-40 animate-pulse rounded bg-muted" />
        ) : performance && performance.trend.length > 0 ? (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart
              data={performance.trend}
              margin={{ top: 4, right: 4, bottom: 0, left: -16 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(240 6% 90%)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "hsl(240 4% 46%)" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: "hsl(240 4% 46%)" }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(0 0% 100%)",
                  border: "1px solid hsl(240 6% 90%)",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                formatter={(v) => [(v as number).toFixed(1), "Avg score"]}
              />
              <ReferenceLine
                y={QUALITY_LINE}
                stroke="hsl(143 64% 24%)"
                strokeDasharray="4 3"
                strokeOpacity={0.6}
              />
              <ReferenceLine
                y={AT_RISK_LINE}
                stroke="hsl(21 88% 40%)"
                strokeDasharray="4 3"
                strokeOpacity={0.6}
              />
              <Line
                type="monotone"
                dataKey="avg_overall_score"
                stroke="hsl(170 61% 26%)"
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div
            data-testid="trend-empty"
            className="flex h-40 items-center justify-center text-sm text-muted-foreground"
          >
            No trend data available.
          </div>
        )}
      </div>

      {/* Dimension breakdown + vs team in columns */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div
          data-testid="dimension-card"
          className="rounded-lg border border-border bg-card p-5 shadow-sm"
        >
          <h3 className="mb-3 text-sm font-semibold text-foreground">
            Dimension Breakdown
          </h3>
          {loadingPerf ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-4 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : performance ? (
            <DimensionBreakdown items={performance.dimension_breakdown} />
          ) : null}
        </div>

        {loadingPerf ? (
          <CardSkeleton height="h-48" data-testid="card-skeleton" />
        ) : performance ? (
          <VsTeamCard data={performance.vs_team} />
        ) : null}
      </div>

      {/* Coaching panel */}
      {loadingCoaching ? (
        <CardSkeleton height="h-48" data-testid="card-skeleton" />
      ) : coaching ? (
        <CoachingPanel agentId={id} notes={coaching.items} />
      ) : null}
    </div>
  );
}

export default function AgentDetailPage() {
  return (
    <Suspense>
      <AgentDetailContent />
    </Suspense>
  );
}
