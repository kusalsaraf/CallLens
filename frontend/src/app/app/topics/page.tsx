"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

import { FilterBar } from "@/components/overview/FilterBar";
import { CardSkeleton } from "@/components/overview/CardSkeleton";
import {
  apiListTeams,
  type AnalyticsFilters,
} from "@/lib/api/analytics";
import {
  apiGetTopicAnalytics,
  type TopicAnalyticsEntry,
} from "@/lib/api/topics";
import {
  apiBandToScoreBand,
  BAND_TEXT_CLASS,
  type ScoreBand,
} from "@/lib/constants/scoreBands";

type SortKey = "call_count" | "avg_overall_score" | "flagged_rate";

const BAND_BAR_COLOR: Record<ScoreBand, string> = {
  quality: "hsl(var(--quality))",
  "at-risk": "hsl(var(--at-risk))",
  fail: "hsl(var(--fail))",
};

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

function filtersToParams(f: AnalyticsFilters): string {
  const p = new URLSearchParams();
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  if (f.team_id) p.set("team_id", f.team_id);
  return p.toString();
}

function TopicsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [filters, setFilters] = useState<AnalyticsFilters>(() =>
    filtersFromParams(searchParams),
  );
  const [sortKey, setSortKey] = useState<SortKey>("call_count");
  const [sortAsc, setSortAsc] = useState(false);

  const updateFilters = useCallback(
    (next: AnalyticsFilters) => {
      setFilters(next);
      router.replace(`/app/topics?${filtersToParams(next)}`);
    },
    [router],
  );

  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: apiListTeams,
    staleTime: 5 * 60 * 1000,
  });

  const {
    data: topicData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["topic-analytics", filters],
    queryFn: () => apiGetTopicAnalytics(filters),
  });

  const sorted = useMemo(() => {
    if (!topicData) return [];
    const items = [...topicData.items];
    items.sort((a, b) => {
      const av = a[sortKey] ?? -1;
      const bv = b[sortKey] ?? -1;
      return sortAsc ? (av > bv ? 1 : -1) : av < bv ? 1 : -1;
    });
    return items;
  }, [topicData, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return "";
    return sortAsc ? " ↑" : " ↓";
  }

  const chartData = useMemo(() => {
    if (!topicData) return [];
    return [...topicData.items]
      .sort((a, b) => b.call_count - a.call_count)
      .slice(0, 10)
      .map((t) => ({
        name: t.name.length > 16 ? t.name.slice(0, 14) + "…" : t.name,
        call_count: t.call_count,
        band: t.band
          ? apiBandToScoreBand(t.band, t.avg_overall_score ?? 0)
          : ("at-risk" as ScoreBand),
      }));
  }, [topicData]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-xl font-bold text-foreground">
          Topics
        </h1>
        <FilterBar
          filters={filters}
          teams={teams ?? null}
          onFiltersChange={updateFilters}
        />
      </div>

      {/* Bar chart — call volume per topic, bars tinted by band */}
      {isLoading ? (
        <CardSkeleton height="h-56" />
      ) : chartData.length > 0 ? (
        <div
          data-testid="topic-chart"
          className="rounded-lg border border-border bg-card p-4"
        >
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
            Call Volume by Topic
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 10 }}>
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tick={{ fontSize: 11 }}
              />
              <Tooltip
                formatter={(value) => [`${value} calls`, "Volume"]}
              />
              <Bar dataKey="call_count" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={BAND_BAR_COLOR[entry.band]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      {/* Error state */}
      {isError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          Failed to load topic analytics. Try refreshing.
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <CardSkeleton height="h-64" />
      ) : sorted.length === 0 && !isError ? (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <p className="text-muted-foreground">
            No topics found in this range.
          </p>
        </div>
      ) : sorted.length > 0 ? (
        <div
          data-testid="topics-table"
          className="overflow-hidden rounded-lg border border-border bg-card"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                  Topic
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-right font-semibold text-muted-foreground tabular"
                  onClick={() => toggleSort("call_count")}
                  data-testid="sort-call-count"
                >
                  Calls{sortIndicator("call_count")}
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-right font-semibold text-muted-foreground tabular"
                  onClick={() => toggleSort("avg_overall_score")}
                  data-testid="sort-avg-score"
                >
                  Avg Score{sortIndicator("avg_overall_score")}
                </th>
                <th
                  className="cursor-pointer px-4 py-3 text-right font-semibold text-muted-foreground tabular"
                  onClick={() => toggleSort("flagged_rate")}
                  data-testid="sort-flagged-rate"
                >
                  Flagged{sortIndicator("flagged_rate")}
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((t: TopicAnalyticsEntry, idx: number) => {
                const band = t.band
                  ? apiBandToScoreBand(t.band, t.avg_overall_score ?? 0)
                  : null;
                const flaggedPct =
                  t.flagged_rate != null
                    ? `${(t.flagged_rate * 100).toFixed(1)}%`
                    : "—";
                const flaggedBand: ScoreBand | null =
                  t.flagged_rate != null && t.flagged_rate > 0.5
                    ? "fail"
                    : t.flagged_rate != null && t.flagged_rate > 0.2
                      ? "at-risk"
                      : null;

                return (
                  <tr
                    key={t.topic_id}
                    className={`transition-colors hover:bg-muted/30 ${
                      idx < sorted.length - 1 ? "border-b border-border" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/app/calls?topic_id=${t.topic_id}`}
                        className="font-medium text-foreground hover:text-primary hover:underline"
                        data-testid={`topic-link-${t.slug}`}
                      >
                        {t.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right tabular text-muted-foreground">
                      {t.call_count}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular font-semibold ${
                        band ? BAND_TEXT_CLASS[band] : "text-muted-foreground"
                      }`}
                    >
                      {t.avg_overall_score != null
                        ? t.avg_overall_score.toFixed(1)
                        : "—"}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular ${
                        flaggedBand
                          ? BAND_TEXT_CLASS[flaggedBand]
                          : "text-muted-foreground"
                      }`}
                    >
                      {flaggedPct}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

export default function TopicsPage() {
  return (
    <Suspense>
      <TopicsContent />
    </Suspense>
  );
}
