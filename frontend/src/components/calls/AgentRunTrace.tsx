"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { apiBandToScoreBand, BAND_TEXT_CLASS } from "@/lib/constants/scoreBands";
import type { TraceOut, AgentRunOut } from "@/lib/api/calls";

interface AgentRunTraceProps {
  trace: TraceOut;
  className?: string;
}

const NODE_DISPLAY_NAMES: Record<string, string> = {
  preprocess: "Preprocess",
  sentiment_empathy: "Sentiment & Empathy",
  script_adherence: "Script Adherence",
  compliance: "Compliance",
  objection_handling: "Objection Handling",
  talk_listen: "Talk / Listen",
  supervisor: "Supervisor",
};

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function NodeName({ node }: { node: string }) {
  return <>{NODE_DISPLAY_NAMES[node] ?? node}</>;
}

/**
 * Collapsible section visualising the multi-agent LangGraph pipeline:
 * preprocess → specialists (parallel) → supervisor.
 * Shows provider, score, confidence, evidence counts, and timing per node.
 */
export function AgentRunTrace({ trace, className }: AgentRunTraceProps) {
  const [open, setOpen] = useState(false);

  const preprocess = trace.runs.find((r) => r.role === "preprocess");
  const specialists = trace.runs.filter((r) => r.role === "specialist");
  const supervisor = trace.runs.find((r) => r.role === "supervisor");

  return (
    <div
      data-testid="agent-run-trace"
      className={cn(
        "rounded-lg border border-border bg-card shadow-sm",
        className,
      )}
    >
      {/* ── Collapsible header ── */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3.5 text-left"
      >
        <div className="flex items-center gap-2">
          {/* Pipeline icon */}
          <svg
            aria-hidden="true"
            className="h-4 w-4 shrink-0 text-primary/70"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M3 12h6M15 12h6M12 3v6M12 15v6" />
          </svg>
          <span className="text-sm font-semibold text-foreground">
            How this score was made
          </span>
          <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] tabular text-muted-foreground">
            {trace.runs.length} agent{trace.runs.length !== 1 ? "s" : ""}
          </span>
        </div>
        <svg
          aria-hidden="true"
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
            open && "rotate-180",
          )}
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 6l4 4 4-4" />
        </svg>
      </button>

      {/* ── Expandable body ── */}
      {open && (
        <div className="border-t border-border px-4 pb-4 pt-3">
          <div className="flex flex-col gap-4">

            {/* Step 1: Preprocess */}
            {preprocess && (
              <PipelineStep label="1 · Preprocess" connector="down">
                <TraceRow run={preprocess} />
              </PipelineStep>
            )}

            {/* Step 2: Specialists (parallel) */}
            {specialists.length > 0 && (
              <PipelineStep
                label="2 · Specialist Analysis (parallel)"
                connector="down"
              >
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                  {specialists.map((r) => (
                    <TraceRow key={r.id} run={r} />
                  ))}
                </div>
              </PipelineStep>
            )}

            {/* Step 3: Supervisor */}
            {supervisor && (
              <PipelineStep label="3 · Supervisor" connector="none">
                <TraceRow run={supervisor} emphasize />
              </PipelineStep>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PipelineStep({
  label,
  children,
  connector,
}: {
  label: string;
  children: React.ReactNode;
  connector: "down" | "none";
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {children}
      {connector === "down" && (
        <div className="flex justify-center py-1" aria-hidden="true">
          <div className="h-5 w-px border-l-2 border-dashed border-border" />
        </div>
      )}
    </div>
  );
}

function TraceRow({
  run,
  emphasize = false,
}: {
  run: AgentRunOut;
  emphasize?: boolean;
}) {
  const band =
    run.score != null ? apiBandToScoreBand(undefined, run.score) : null;
  const scoreTextClass = band ? BAND_TEXT_CLASS[band] : "text-muted-foreground";
  const confidencePct =
    run.confidence != null ? Math.round(run.confidence * 100) : null;

  return (
    <div
      data-testid="trace-row"
      className={cn(
        "flex flex-col gap-2 rounded-lg border border-border p-3 text-xs",
        emphasize && "border-primary/25 bg-primary/5",
      )}
    >
      {/* Node name + duration */}
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-foreground">
          <NodeName node={run.node} />
        </span>
        <span className="tabular text-muted-foreground">
          {formatMs(run.duration_ms)}
        </span>
      </div>

      {/* Provider */}
      <div className="text-muted-foreground">
        <span className="font-medium text-foreground/60">Provider: </span>
        {run.provider}
      </div>

      {/* Score + confidence */}
      {run.score != null && (
        <div className="flex flex-wrap gap-3">
          <span>
            <span className="text-muted-foreground">Score: </span>
            <span className={cn("tabular font-semibold", scoreTextClass)}>
              {run.score}
            </span>
          </span>
          {confidencePct != null && (
            <span>
              <span className="text-muted-foreground">Confidence: </span>
              <span className="tabular font-medium">{confidencePct}%</span>
            </span>
          )}
        </div>
      )}

      {/* Evidence */}
      {(run.evidence_kept > 0 || run.evidence_dropped > 0) && (
        <div className="flex gap-3">
          <span>
            <span className="text-muted-foreground">Evidence: </span>
            <span className="tabular font-medium text-[hsl(var(--quality))]">
              {run.evidence_kept} kept
            </span>
          </span>
          {run.evidence_dropped > 0 && (
            <span className="tabular font-medium text-[hsl(var(--fail))]">
              {run.evidence_dropped} dropped
            </span>
          )}
        </div>
      )}
    </div>
  );
}
