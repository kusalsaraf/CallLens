"use client";

import { cn } from "@/lib/utils";
import { scoreBand, BAND_TEXT_CLASS, BAND_BG_CLASS } from "@/lib/constants/scoreBands";
import type { DimensionBreakdownOut } from "@/lib/api/agents";

interface DimensionBreakdownProps {
  items: DimensionBreakdownOut[];
}

/** Horizontal bar chart of per-dimension avg scores, bars tinted by band. */
export function DimensionBreakdown({ items }: DimensionBreakdownProps) {
  if (items.length === 0) {
    return (
      <div
        data-testid="dimension-empty"
        className="text-sm text-muted-foreground"
      >
        No dimension data available.
      </div>
    );
  }

  return (
    <div
      data-testid="dimension-breakdown"
      className="flex flex-col gap-3"
    >
      {items.map((d) => {
        const band = scoreBand(d.avg_score);
        const textClass = BAND_TEXT_CLASS[band];
        const bgClass = BAND_BG_CLASS[band];
        const pct = Math.min(100, Math.max(0, d.avg_score));

        return (
          <div key={d.dimension_key} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-foreground">{d.dimension_name}</span>
              <span className={cn("tabular font-semibold", textClass)}>
                {d.avg_score.toFixed(1)}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                data-testid={`bar-${d.dimension_key}`}
                className={cn("h-full rounded-full transition-all", bgClass)}
                style={{ width: `${pct}%`, opacity: 0.85 }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
