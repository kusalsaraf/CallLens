"use client";

import { cn } from "@/lib/utils";
import { scoreBand, BAND_TEXT_CLASS } from "@/lib/constants/scoreBands";
import type { VsTeamOut } from "@/lib/api/agents";

interface VsTeamCardProps {
  data: VsTeamOut;
}

/** Side-by-side comparison of agent avg score vs their team avg. */
export function VsTeamCard({ data }: VsTeamCardProps) {
  const agentBand = scoreBand(data.agent_avg);
  const teamBand = scoreBand(data.team_avg);
  const delta = data.agent_avg - data.team_avg;
  const deltaStr = delta >= 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1);
  const deltaClass =
    delta >= 0 ? "text-[hsl(143_64%_24%)]" : "text-[hsl(346_80%_35%)]";

  return (
    <div
      data-testid="vs-team-card"
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      <h3 className="text-sm font-semibold text-foreground">Agent vs Team</h3>

      <div className="flex items-end gap-6">
        {/* Agent bar */}
        <div className="flex flex-1 flex-col items-center gap-2">
          <span
            data-testid="vs-agent-score"
            className={cn("tabular text-2xl font-bold", BAND_TEXT_CLASS[agentBand])}
          >
            {data.agent_avg.toFixed(1)}
          </span>
          <div className="w-full rounded-md bg-muted" style={{ height: 80 }}>
            <div
              data-testid="vs-agent-bar"
              className="w-full rounded-md transition-all"
              style={{
                height: `${(data.agent_avg / 100) * 80}px`,
                background: "hsl(143 64% 24%)",
                opacity: 0.7,
              }}
            />
          </div>
          <span className="text-xs font-medium text-foreground">Agent</span>
        </div>

        {/* Team bar */}
        <div className="flex flex-1 flex-col items-center gap-2">
          <span
            data-testid="vs-team-score"
            className={cn("tabular text-2xl font-bold", BAND_TEXT_CLASS[teamBand])}
          >
            {data.team_avg.toFixed(1)}
          </span>
          <div className="w-full rounded-md bg-muted" style={{ height: 80 }}>
            <div
              data-testid="vs-team-bar"
              className="w-full rounded-md transition-all"
              style={{
                height: `${(data.team_avg / 100) * 80}px`,
                background: "hsl(240 6% 50%)",
                opacity: 0.7,
              }}
            />
          </div>
          <span className="text-xs font-medium text-foreground">Team avg</span>
        </div>

        {/* Delta */}
        <div className="flex flex-col items-center gap-1 pb-6">
          <span
            data-testid="vs-delta"
            className={cn("tabular text-lg font-bold", deltaClass)}
          >
            {deltaStr}
          </span>
          <span className="text-xs text-muted-foreground">vs team</span>
        </div>
      </div>
    </div>
  );
}
