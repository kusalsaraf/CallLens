"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";
import type { ScoreDistributionOut } from "@/lib/api/analytics";

interface ScoreDistributionChartProps {
  data: ScoreDistributionOut;
}

/** Map a histogram bucket's midpoint to the canonical band color. */
function bucketColor(bucketStart: number): string {
  if (bucketStart >= 80) return "hsl(143 64% 24%)";
  if (bucketStart >= 60) return "hsl(21 88% 40%)";
  return "hsl(346 80% 35%)";
}

/** Bar histogram of score distribution, bars tinted by canonical band color. */
export function ScoreDistributionChart({ data }: ScoreDistributionChartProps) {
  const { buckets, bands } = data;

  return (
    <div
      data-testid="score-distribution-chart"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Score Distribution</h3>
        <div className="flex gap-3 text-xs text-muted-foreground">
          <span data-testid="band-quality" className="text-[hsl(143_64%_24%)]">
            Quality: {bands.quality}
          </span>
          <span data-testid="band-at-risk" className="text-[hsl(21_88%_40%)]">
            At-risk: {bands.at_risk}
          </span>
          <span data-testid="band-fail" className="text-[hsl(346_80%_35%)]">
            Fail: {bands.fail}
          </span>
        </div>
      </div>

      {buckets.length === 0 ? (
        <div
          data-testid="distribution-empty"
          className="flex h-48 items-center justify-center text-sm text-muted-foreground"
        >
          No scored calls in this range.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={buckets} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(240 6% 90%)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: "hsl(240 4% 46%)" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              allowDecimals={false}
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
              formatter={(v) => [v as number, "Calls"]}
            />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
              {buckets.map((b) => (
                <Cell
                  key={b.bucket}
                  fill={bucketColor(b.bucket)}
                  data-testid={`bar-bucket-${b.bucket}`}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
