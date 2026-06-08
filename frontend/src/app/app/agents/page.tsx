"use client";

import { Suspense, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { FilterBar } from "@/components/overview/FilterBar";
import { CardSkeleton } from "@/components/overview/CardSkeleton";
import {
  scoreBand,
  BAND_TEXT_CLASS,
} from "@/lib/constants/scoreBands";
import { apiGetLeaderboard, apiListTeams, type AnalyticsFilters, type LeaderboardEntryOut } from "@/lib/api/analytics";

type SortCol = "rank" | "name" | "team" | "calls_scored" | "avg_overall_score" | "compliance_pass_rate";
type SortDir = "asc" | "desc";

function defaultFilters(): AnalyticsFilters {
  const today = new Date();
  const from = new Date();
  from.setDate(today.getDate() - 30);
  return {
    date_from: from.toISOString().slice(0, 10),
    date_to: today.toISOString().slice(0, 10),
  };
}

function filtersFromParams(params: URLSearchParams): AnalyticsFilters {
  const f: AnalyticsFilters = {};
  if (params.get("date_from")) f.date_from = params.get("date_from")!;
  if (params.get("date_to")) f.date_to = params.get("date_to")!;
  if (params.get("team_id")) f.team_id = params.get("team_id")!;
  return Object.keys(f).length > 0 ? f : defaultFilters();
}

function filtersToQs(f: AnalyticsFilters): string {
  const p = new URLSearchParams();
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  if (f.team_id) p.set("team_id", f.team_id);
  return p.toString();
}

function sortEntries(
  items: LeaderboardEntryOut[],
  col: SortCol,
  dir: SortDir,
): LeaderboardEntryOut[] {
  return [...items].sort((a, b) => {
    let av: string | number;
    let bv: string | number;
    if (col === "rank") { av = 0; bv = 0; }
    else if (col === "name") { av = a.name; bv = b.name; }
    else if (col === "team") { av = a.team; bv = b.team; }
    else if (col === "calls_scored") { av = a.calls_scored; bv = b.calls_scored; }
    else if (col === "compliance_pass_rate") { av = a.compliance_pass_rate; bv = b.compliance_pass_rate; }
    else { av = a.avg_overall_score; bv = b.avg_overall_score; }

    if (typeof av === "string") {
      const cmp = av.localeCompare(bv as string);
      return dir === "asc" ? cmp : -cmp;
    }
    return dir === "asc" ? av - (bv as number) : (bv as number) - av;
  });
}

function SortIcon({ col, active, dir }: { col: string; active: string; dir: SortDir }) {
  if (col !== active) return <span className="opacity-30">↕</span>;
  return <span>{dir === "asc" ? "↑" : "↓"}</span>;
}

function LeaderboardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [filters, setFilters] = useState<AnalyticsFilters>(() =>
    filtersFromParams(searchParams),
  );
  const [sortCol, setSortCol] = useState<SortCol>("avg_overall_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const updateFilters = useCallback(
    (next: AnalyticsFilters) => {
      setFilters(next);
      router.replace(`/app/agents?${filtersToQs(next)}`);
    },
    [router],
  );

  function handleSort(col: SortCol) {
    if (col === sortCol) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("desc");
    }
  }

  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: apiListTeams,
    staleTime: 5 * 60 * 1000,
  });

  const { data: leaderboard, isLoading } = useQuery({
    queryKey: ["leaderboard", filters],
    queryFn: () => apiGetLeaderboard(filters),
  });

  const sorted = leaderboard ? sortEntries(leaderboard.items, sortCol, sortDir) : [];

  const thClass =
    "cursor-pointer select-none whitespace-nowrap pb-2 text-left text-xs font-medium text-muted-foreground hover:text-foreground";

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-foreground">Agents</h1>
        <FilterBar
          filters={filters}
          teams={teams ?? null}
          onFiltersChange={updateFilters}
        />
      </div>

      {isLoading ? (
        <CardSkeleton height="h-64" data-testid="leaderboard-skeleton" />
      ) : sorted.length === 0 ? (
        <div
          data-testid="leaderboard-empty"
          className="rounded-lg border border-border bg-card p-10 text-center text-sm text-muted-foreground"
        >
          No agents with scored calls in this range.
        </div>
      ) : (
        <div
          data-testid="leaderboard-table"
          className="overflow-x-auto rounded-lg border border-border bg-card shadow-sm"
        >
          <table className="w-full text-sm">
            <thead className="border-b border-border">
              <tr>
                <th className={cn(thClass, "pl-5 pr-3")} onClick={() => handleSort("rank")}>
                  # <SortIcon col="rank" active={sortCol} dir={sortDir} />
                </th>
                <th className={cn(thClass, "pr-4")} onClick={() => handleSort("name")}>
                  Agent <SortIcon col="name" active={sortCol} dir={sortDir} />
                </th>
                <th className={cn(thClass, "pr-4")} onClick={() => handleSort("team")}>
                  Team <SortIcon col="team" active={sortCol} dir={sortDir} />
                </th>
                <th className={cn(thClass, "pr-4")} onClick={() => handleSort("calls_scored")}>
                  Calls <SortIcon col="calls_scored" active={sortCol} dir={sortDir} />
                </th>
                <th className={cn(thClass, "pr-4")} onClick={() => handleSort("avg_overall_score")}>
                  Avg Score <SortIcon col="avg_overall_score" active={sortCol} dir={sortDir} />
                </th>
                <th className={cn(thClass, "pr-5")} onClick={() => handleSort("compliance_pass_rate")}>
                  Compliance <SortIcon col="compliance_pass_rate" active={sortCol} dir={sortDir} />
                </th>
                <th className={cn(thClass, "pr-5")}>Status</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((entry, i) => {
                const band = scoreBand(entry.avg_overall_score);
                const textClass = BAND_TEXT_CLASS[band];
                return (
                  <tr
                    key={entry.agent_id}
                    data-testid={`leaderboard-row-${entry.agent_id}`}
                    onClick={() => router.push(`/app/agents/${entry.agent_id}`)}
                    className="cursor-pointer border-b border-border/50 hover:bg-muted/40 transition-colors last:border-0"
                  >
                    <td className="py-3 pl-5 pr-3 tabular text-muted-foreground">
                      {i + 1}
                    </td>
                    <td className="py-3 pr-4 font-medium">
                      <Link
                        href={`/app/agents/${entry.agent_id}`}
                        className="hover:underline text-foreground"
                        onClick={(e) => e.stopPropagation()}
                        data-testid={`agent-link-${entry.agent_id}`}
                      >
                        {entry.name}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-muted-foreground">{entry.team}</td>
                    <td className="py-3 pr-4 tabular">{entry.calls_scored}</td>
                    <td className={cn("py-3 pr-4 tabular font-semibold", textClass)}>
                      {entry.avg_overall_score.toFixed(1)}
                    </td>
                    <td className="py-3 pr-5 tabular">
                      {(entry.compliance_pass_rate * 100).toFixed(0)}%
                    </td>
                    <td className="py-3 pr-5">
                      {entry.is_at_risk ? (
                        <span
                          data-testid={`at-risk-badge-${entry.agent_id}`}
                          className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium bg-[hsl(var(--at-risk)/0.08)] text-[hsl(var(--at-risk))]"
                        >
                          At-risk
                        </span>
                      ) : (
                        <span
                          data-testid={`quality-badge-${entry.agent_id}`}
                          className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium bg-quality/10 text-quality"
                        >
                          On track
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function AgentsPage() {
  return (
    <Suspense>
      <LeaderboardContent />
    </Suspense>
  );
}
