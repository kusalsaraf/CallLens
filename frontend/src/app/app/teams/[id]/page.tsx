"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { CardSkeleton } from "@/components/overview/CardSkeleton";
import { scoreBand, BAND_TEXT_CLASS } from "@/lib/constants/scoreBands";
import { apiListTeams } from "@/lib/api/analytics";
import { apiGetTeamAnalytics } from "@/lib/api/teams";
import { ApiError } from "@/lib/api/client";

const BAND_COLOR: Record<string, string> = {
  quality: "hsl(143 64% 24%)",
  "at-risk": "hsl(21 88% 40%)",
  fail: "hsl(346 80% 35%)",
};

function TeamDetailContent() {
  const { id } = useParams<{ id: string }>();

  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: apiListTeams,
    staleTime: 5 * 60 * 1000,
  });

  const {
    data: analytics,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["team-analytics", id],
    queryFn: () => apiGetTeamAnalytics(id),
    retry: (count, err) => {
      if (err instanceof ApiError && err.status === 404) return false;
      return count < 2;
    },
  });

  // 404 state
  if (error instanceof ApiError && error.status === 404) {
    return (
      <div
        data-testid="team-not-found"
        className="flex flex-col items-center justify-center gap-4 p-16 text-center"
      >
        <span className="text-4xl">🔍</span>
        <h2 className="text-lg font-semibold text-foreground">Team not found</h2>
        <p className="text-sm text-muted-foreground">
          This team doesn&apos;t exist or has been removed.
        </p>
        <Link
          href="/app/teams"
          className="text-sm text-primary underline-offset-2 hover:underline"
        >
          ← Back to Teams
        </Link>
      </div>
    );
  }

  const teamName = teams?.items.find((t) => t.id === id)?.name ?? "Team";
  const avgBand = analytics?.avg_overall_score != null
    ? scoreBand(analytics.avg_overall_score)
    : null;

  // Distribution bar widths
  const dist = analytics?.score_distribution;
  const distTotal = dist ? dist.quality + dist.at_risk + dist.fail : 0;
  const distPct = (n: number) =>
    distTotal > 0 ? `${((n / distTotal) * 100).toFixed(1)}%` : "0%";

  return (
    <div className="flex flex-col gap-6 p-6">
      <Link
        href="/app/teams"
        className="self-start text-sm text-muted-foreground hover:text-foreground"
      >
        ← Teams
      </Link>

      {/* Header stats */}
      {isLoading ? (
        <CardSkeleton height="h-24" data-testid="card-skeleton" />
      ) : analytics ? (
        <div
          data-testid="team-header"
          className="flex flex-wrap items-center gap-6 rounded-lg border border-border bg-card p-5 shadow-sm"
        >
          <div className="flex-1 min-w-0">
            <h1
              data-testid="team-name"
              className="text-xl font-bold text-foreground"
            >
              {teamName}
            </h1>
          </div>
          <div className="flex items-center gap-8">
            <div className="text-center">
              <p className="text-xs text-muted-foreground">Calls Scored</p>
              <p
                data-testid="team-calls-scored"
                className="tabular text-xl font-bold text-foreground"
              >
                {analytics.calls_scored}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-muted-foreground">Avg Score</p>
              <p
                data-testid="team-avg-score"
                className={cn(
                  "tabular text-xl font-bold",
                  avgBand ? BAND_TEXT_CLASS[avgBand] : "text-foreground",
                )}
              >
                {analytics.avg_overall_score != null
                  ? analytics.avg_overall_score.toFixed(1)
                  : "—"}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-muted-foreground">Compliance</p>
              <p
                data-testid="team-compliance"
                className="tabular text-xl font-bold text-foreground"
              >
                {analytics.compliance_pass_rate != null
                  ? `${Math.round(analytics.compliance_pass_rate * 100)}%`
                  : "—"}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {/* Score distribution */}
      {isLoading ? (
        <CardSkeleton height="h-32" data-testid="card-skeleton" />
      ) : analytics ? (
        <div
          data-testid="team-distribution"
          className="rounded-lg border border-border bg-card p-5 shadow-sm"
        >
          <h3 className="mb-4 text-sm font-semibold text-foreground">
            Score Distribution
          </h3>
          <div className="flex h-6 w-full overflow-hidden rounded-full">
            {dist && distTotal > 0 ? (
              <>
                <div
                  data-testid="dist-quality"
                  style={{
                    width: distPct(dist.quality),
                    background: BAND_COLOR.quality,
                    opacity: 0.8,
                  }}
                  title={`Quality: ${dist.quality}`}
                />
                <div
                  data-testid="dist-at-risk"
                  style={{
                    width: distPct(dist.at_risk),
                    background: BAND_COLOR["at-risk"],
                    opacity: 0.8,
                  }}
                  title={`At-risk: ${dist.at_risk}`}
                />
                <div
                  data-testid="dist-fail"
                  style={{
                    width: distPct(dist.fail),
                    background: BAND_COLOR.fail,
                    opacity: 0.8,
                  }}
                  title={`Fail: ${dist.fail}`}
                />
              </>
            ) : (
              <div className="flex-1 bg-muted" />
            )}
          </div>
          {dist && (
            <div className="mt-2 flex gap-4 text-xs text-muted-foreground">
              <span className="text-[hsl(143_64%_24%)]">Quality: {dist.quality}</span>
              <span className="text-[hsl(21_88%_40%)]">At-risk: {dist.at_risk}</span>
              <span className="text-[hsl(346_80%_35%)]">Fail: {dist.fail}</span>
            </div>
          )}
        </div>
      ) : null}

      {/* Agent comparison */}
      {isLoading ? (
        <CardSkeleton height="h-48" data-testid="card-skeleton" />
      ) : analytics && analytics.agent_comparison.length > 0 ? (
        <div
          data-testid="agent-comparison"
          className="rounded-lg border border-border bg-card shadow-sm"
        >
          <div className="border-b border-border px-5 py-3">
            <h3 className="text-sm font-semibold text-foreground">Agents</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium text-muted-foreground">
                <th className="py-2 pl-5 pr-4">#</th>
                <th className="py-2 pr-4">Agent</th>
                <th className="py-2 pr-4">Calls Scored</th>
                <th className="py-2 pr-5">Avg Score</th>
              </tr>
            </thead>
            <tbody>
              {analytics.agent_comparison.map((a, i) => {
                const ab = scoreBand(a.avg_overall_score);
                return (
                  <tr
                    key={a.agent_id}
                    data-testid={`agent-row-${a.agent_id}`}
                    className="border-b border-border/50 last:border-0 hover:bg-muted/40 transition-colors"
                  >
                    <td className="py-2 pl-5 pr-4 tabular text-muted-foreground">
                      {i + 1}
                    </td>
                    <td className="py-2 pr-4 font-medium">
                      <Link
                        href={`/app/agents/${a.agent_id}`}
                        data-testid={`agent-comparison-link-${a.agent_id}`}
                        className="hover:underline text-foreground"
                      >
                        {a.name}
                      </Link>
                    </td>
                    <td className="py-2 pr-4 tabular">{a.calls_scored}</td>
                    <td className={cn("py-2 pr-5 tabular font-semibold", BAND_TEXT_CLASS[ab])}>
                      {a.avg_overall_score.toFixed(1)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : analytics && analytics.agent_comparison.length === 0 ? (
        <div
          data-testid="agent-comparison-empty"
          className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground"
        >
          No agents with scored calls in this team.
        </div>
      ) : null}
    </div>
  );
}

export default function TeamDetailPage() {
  return (
    <Suspense>
      <TeamDetailContent />
    </Suspense>
  );
}
