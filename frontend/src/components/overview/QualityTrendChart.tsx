"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { QualityTrendsOut } from "@/lib/api/analytics";

interface QualityTrendChartProps {
  data: QualityTrendsOut;
  bucket: "day" | "week";
  onBucketChange: (b: "day" | "week") => void;
}

const QUALITY_LINE = 80;
const AT_RISK_LINE = 60;

/** Area chart of avg overall score over time with canonical band reference lines. */
export function QualityTrendChart({
  data,
  bucket,
  onBucketChange,
}: QualityTrendChartProps) {
  const points = data.items.map((pt) => ({
    date: pt.date,
    score: pt.avg_overall_score,
    calls: pt.calls_scored,
  }));

  return (
    <div
      data-testid="quality-trend-chart"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Quality Trend</h3>
        <div className="flex gap-1 rounded-md border border-border p-0.5">
          {(["day", "week"] as const).map((b) => (
            <button
              key={b}
              data-testid={`bucket-${b}`}
              onClick={() => onBucketChange(b)}
              className={
                bucket === b
                  ? "rounded px-3 py-1 text-xs font-medium bg-primary text-primary-foreground"
                  : "rounded px-3 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
              }
            >
              {b === "day" ? "Daily" : "Weekly"}
            </button>
          ))}
        </div>
      </div>

      {points.length === 0 ? (
        <div
          data-testid="trend-empty"
          className="flex h-48 items-center justify-center text-sm text-muted-foreground"
        >
          No scored calls in this range.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
            <defs>
              <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(170 61% 26%)" stopOpacity={0.18} />
                <stop offset="95%" stopColor="hsl(170 61% 26%)" stopOpacity={0} />
              </linearGradient>
            </defs>
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
            {/* Canonical band thresholds — quality ≥80, at-risk 60-79 */}
            <ReferenceLine
              y={QUALITY_LINE}
              stroke="hsl(143 64% 24%)"
              strokeDasharray="4 3"
              strokeOpacity={0.6}
              label={{ value: "Quality", position: "right", fontSize: 9, fill: "hsl(143 64% 24%)" }}
            />
            <ReferenceLine
              y={AT_RISK_LINE}
              stroke="hsl(21 88% 40%)"
              strokeDasharray="4 3"
              strokeOpacity={0.6}
              label={{ value: "At-risk", position: "right", fontSize: 9, fill: "hsl(21 88% 40%)" }}
            />
            <Area
              type="monotone"
              dataKey="score"
              stroke="hsl(170 61% 26%)"
              strokeWidth={2}
              fill="url(#scoreGrad)"
              dot={false}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}

      {/* Legend */}
      <div className="flex gap-4 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 bg-[hsl(143_64%_24%)] opacity-60" />
          Quality ≥80
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 bg-[hsl(21_88%_40%)] opacity-60" />
          At-risk ≥60
        </span>
      </div>
    </div>
  );
}
