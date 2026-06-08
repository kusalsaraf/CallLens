"use client";

import { Suspense, useCallback, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { CardSkeleton } from "@/components/overview/CardSkeleton";
import { KpiCards } from "@/components/overview/KpiCards";
import { QualityTrendChart } from "@/components/overview/QualityTrendChart";
import { ScoreDistributionChart } from "@/components/overview/ScoreDistributionChart";
import { ComplianceCard } from "@/components/overview/ComplianceCard";
import { FlaggedCallsTable } from "@/components/overview/FlaggedCallsTable";
import { FilterBar } from "@/components/overview/FilterBar";

import {
  apiGetOverview,
  apiGetQualityTrends,
  apiGetScoreDistribution,
  apiGetCompliance,
  apiGetFlagged,
  apiListTeams,
  type AnalyticsFilters,
} from "@/lib/api/analytics";

const FLAGGED_PAGE_SIZE = 10;

/** Default to Last 30 days. */
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
  if (params.get("agent_id")) f.agent_id = params.get("agent_id")!;
  return Object.keys(f).length > 0 ? f : defaultFilters();
}

function filtersToParams(f: AnalyticsFilters): string {
  const p = new URLSearchParams();
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  if (f.team_id) p.set("team_id", f.team_id);
  if (f.agent_id) p.set("agent_id", f.agent_id);
  return p.toString();
}

function OverviewContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [filters, setFilters] = useState<AnalyticsFilters>(() =>
    filtersFromParams(searchParams),
  );
  const [bucket, setBucket] = useState<"day" | "week">("day");
  const [flaggedOffset, setFlaggedOffset] = useState(0);

  const updateFilters = useCallback(
    (next: AnalyticsFilters) => {
      setFilters(next);
      setFlaggedOffset(0);
      router.replace(`/app/overview?${filtersToParams(next)}`);
    },
    [router],
  );

  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: apiListTeams,
    staleTime: 5 * 60 * 1000,
  });

  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ["overview", filters],
    queryFn: () => apiGetOverview(filters),
  });

  const { data: trends, isLoading: loadingTrends } = useQuery({
    queryKey: ["quality-trends", filters, bucket],
    queryFn: () => apiGetQualityTrends(filters, bucket),
  });

  const { data: distribution, isLoading: loadingDist } = useQuery({
    queryKey: ["score-distribution", filters],
    queryFn: () => apiGetScoreDistribution(filters),
  });

  const { data: compliance, isLoading: loadingCompliance } = useQuery({
    queryKey: ["compliance", filters],
    queryFn: () => apiGetCompliance(filters),
  });

  const { data: flagged, isLoading: loadingFlagged } = useQuery({
    queryKey: ["flagged", filters, flaggedOffset],
    queryFn: () => apiGetFlagged(filters, FLAGGED_PAGE_SIZE, flaggedOffset),
  });

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">Overview</h1>
        <FilterBar
          filters={filters}
          teams={teams ?? null}
          onFiltersChange={updateFilters}
        />
      </div>

      {/* KPI Row */}
      {loadingOverview ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" data-testid="kpi-skeleton">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} data-testid="card-skeleton" />
          ))}
        </div>
      ) : overview ? (
        <KpiCards data={overview} />
      ) : null}

      {/* Charts row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {loadingTrends ? (
          <CardSkeleton height="h-64" data-testid="card-skeleton" />
        ) : trends ? (
          <QualityTrendChart
            data={trends}
            bucket={bucket}
            onBucketChange={setBucket}
          />
        ) : null}

        {loadingDist ? (
          <CardSkeleton height="h-64" data-testid="card-skeleton" />
        ) : distribution ? (
          <ScoreDistributionChart data={distribution} />
        ) : null}
      </div>

      {/* Compliance sparkline */}
      {loadingCompliance ? (
        <CardSkeleton height="h-32" data-testid="card-skeleton" />
      ) : compliance ? (
        <ComplianceCard data={compliance} />
      ) : null}

      {/* Flagged calls */}
      {loadingFlagged ? (
        <CardSkeleton height="h-48" data-testid="card-skeleton" />
      ) : flagged ? (
        <FlaggedCallsTable
          data={flagged}
          onShowMore={() => setFlaggedOffset((o) => o + FLAGGED_PAGE_SIZE)}
        />
      ) : null}
    </div>
  );
}

export default function OverviewPage() {
  return (
    <Suspense>
      <OverviewContent />
    </Suspense>
  );
}
