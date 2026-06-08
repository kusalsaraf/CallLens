"use client";

import {
  LineChart,
  Line,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { ComplianceOut } from "@/lib/api/analytics";

interface ComplianceCardProps {
  data: ComplianceOut;
}

/** Compliance pass-rate card with a mini sparkline trend. */
export function ComplianceCard({ data }: ComplianceCardProps) {
  const pct =
    data.pass_rate != null ? `${Math.round(data.pass_rate * 100)}%` : "—";
  const sparkPoints = data.trend.map((pt) => ({ date: pt.date, v: pt.pass_rate * 100 }));

  return (
    <div
      data-testid="compliance-card"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Compliance</h3>
        <span
          data-testid="compliance-pct"
          className="tabular text-2xl font-bold text-foreground"
        >
          {pct}
        </span>
      </div>

      <p className="text-xs text-muted-foreground">Pass rate over selected period</p>

      {sparkPoints.length > 0 ? (
        <ResponsiveContainer width="100%" height={48}>
          <LineChart data={sparkPoints} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
            <Tooltip
              contentStyle={{
                background: "hsl(0 0% 100%)",
                border: "1px solid hsl(240 6% 90%)",
                borderRadius: 6,
                fontSize: 11,
              }}
              formatter={(v) => [`${(v as number).toFixed(0)}%`, "Pass rate"]}
            />
            <Line
              type="monotone"
              dataKey="v"
              stroke="hsl(143 64% 24%)"
              strokeWidth={1.5}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div
          data-testid="compliance-empty"
          className="text-xs text-muted-foreground"
        >
          No trend data available.
        </div>
      )}
    </div>
  );
}
