"use client";

import { cn } from "@/lib/utils";
import { formatDuration } from "@/lib/utils";
import type { CallAnalysisOut } from "@/lib/api/calls";

interface ConversationDynamicsProps {
  analysis: CallAnalysisOut;
  className?: string;
}

/**
 * Panel showing conversation dynamics: agent/customer talk-listen split bar,
 * interruption count, longest monologue, and total turn count.
 * All numeric values use tabular-nums.
 */
export function ConversationDynamics({
  analysis,
  className,
}: ConversationDynamicsProps) {
  const ratio = analysis.talk_listen_ratio ?? 0;
  // ratio = agent_ms / customer_ms; convert to percentage of total talk time
  const total = ratio + 1;
  const agentPct = Math.round((ratio / total) * 100);
  const customerPct = 100 - agentPct;

  const longestSec = analysis.longest_monologue_ms
    ? analysis.longest_monologue_ms / 1000
    : null;

  return (
    <div
      data-testid="conversation-dynamics"
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-border bg-card p-4 shadow-sm",
        className,
      )}
    >
      <h3 className="text-sm font-semibold text-foreground">
        Conversation Dynamics
      </h3>

      {/* ── Talk / Listen split bar ── */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Agent</span>
          <span>Customer</span>
        </div>
        <div
          data-testid="talk-listen-bar"
          className="relative flex h-3 overflow-hidden rounded-full bg-muted"
          title={`Agent ${agentPct}% · Customer ${customerPct}%`}
        >
          <div
            className="h-full rounded-l-full bg-[hsl(var(--primary)/0.7)] transition-all"
            style={{ width: `${agentPct}%` }}
          />
          <div
            className="h-full flex-1 rounded-r-full bg-[hsl(var(--at-risk)/0.45)]"
          />
        </div>
        <div className="flex justify-between text-[11px] tabular text-muted-foreground">
          <span>{agentPct}%</span>
          <span>{customerPct}%</span>
        </div>
      </div>

      {/* ── Metric grid ── */}
      <div className="grid grid-cols-3 gap-3">
        <MetricTile
          label="Interruptions"
          value={String(analysis.interruptions ?? 0)}
          testId="interruptions-value"
        />
        <MetricTile
          label="Longest monologue"
          value={formatDuration(longestSec)}
          testId="monologue-value"
        />
        <MetricTile
          label="Total turns"
          value={String(analysis.total_turns ?? 0)}
          testId="turns-value"
        />
      </div>
    </div>
  );
}

function MetricTile({
  label,
  value,
  testId,
}: {
  label: string;
  value: string;
  testId?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg bg-muted/50 px-2 py-3 text-center">
      <span
        data-testid={testId}
        className="tabular text-lg font-bold text-foreground"
      >
        {value}
      </span>
      <span className="text-[10px] leading-tight text-muted-foreground">
        {label}
      </span>
    </div>
  );
}
