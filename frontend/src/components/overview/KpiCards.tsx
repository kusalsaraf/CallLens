"use client";

import { cn } from "@/lib/utils";
import { apiBandToScoreBand, BAND_TEXT_CLASS } from "@/lib/constants/scoreBands";
import type { OverviewOut } from "@/lib/api/analytics";

interface KpiCardProps {
  label: string;
  value: React.ReactNode;
  sub?: string;
  className?: string;
  "data-testid"?: string;
}

function KpiCard({ label, value, sub, className, "data-testid": testId }: KpiCardProps) {
  return (
    <div
      data-testid={testId}
      className={cn(
        "flex flex-col gap-2 rounded-lg border border-border bg-card p-5 shadow-sm",
        className,
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="tabular text-3xl font-bold leading-none text-foreground">{value}</div>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

interface KpiCardsProps {
  data: OverviewOut;
}

/** Row of four KPI cards: calls, avg quality, compliance, flagged. */
export function KpiCards({ data }: KpiCardsProps) {
  const avgScore = data.avg_overall_score;
  const band = avgScore != null ? apiBandToScoreBand(undefined, avgScore) : null;
  const scoreColor = band ? BAND_TEXT_CLASS[band] : "text-foreground";

  const compliancePct =
    data.compliance_pass_rate != null
      ? `${Math.round(data.compliance_pass_rate * 100)}%`
      : "—";

  const flagColor =
    data.flagged_count === 0
      ? "text-[hsl(var(--quality))]"
      : data.flagged_count > 5
        ? "text-[hsl(var(--fail))]"
        : "text-[hsl(var(--at-risk))]";

  return (
    <div
      data-testid="kpi-cards"
      className="grid grid-cols-2 gap-4 lg:grid-cols-4"
    >
      <KpiCard
        data-testid="kpi-calls"
        label="Calls Processed"
        value={
          <span>
            <span className="tabular">{data.calls_scored}</span>
            <span className="text-lg font-medium text-muted-foreground">
              /{data.calls_total}
            </span>
          </span>
        }
        sub="scored / total"
      />
      <KpiCard
        data-testid="kpi-avg-score"
        label="Avg Quality Score"
        value={
          <span className={cn("tabular", scoreColor)}>
            {avgScore != null ? avgScore.toFixed(1) : "—"}
          </span>
        }
        sub={band ? `Band: ${band}` : "No scored calls"}
      />
      <KpiCard
        data-testid="kpi-compliance"
        label="Compliance Rate"
        value={<span className="tabular">{compliancePct}</span>}
        sub={
          data.calls_scored > 0
            ? `${data.calls_scored} scored calls`
            : "No scored calls"
        }
      />
      <KpiCard
        data-testid="kpi-flagged"
        label="Flagged / At-Risk"
        value={<span className={cn("tabular", flagColor)}>{data.flagged_count}</span>}
        sub="score < 80 or escalated"
      />
    </div>
  );
}
