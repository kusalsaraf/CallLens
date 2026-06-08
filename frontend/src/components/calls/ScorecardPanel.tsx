"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGetScores } from "@/lib/api/calls";
import type { CallStatus, SegmentOut } from "@/lib/api/calls";
import { cn } from "@/lib/utils";
import { DimensionScoreCard } from "./DimensionScoreCard";

interface ScorecardPanelProps {
  callId: string;
  callStatus: CallStatus;
  segments: SegmentOut[];
  onEvidenceClick?: (segmentId: string, startMs: number) => void;
  className?: string;
}

const PRE_SCORING_STATUSES = new Set<CallStatus>([
  "uploaded",
  "transcribing",
  "diarizing",
  "transcribed",
]);

/**
 * Panel that fetches and renders all scored dimensions for a call.
 * Handles the full status lifecycle: pre-processing, scoring-in-progress,
 * loading, scored, and error states.
 */
export function ScorecardPanel({
  callId,
  callStatus,
  segments,
  onEvidenceClick,
  className,
}: ScorecardPanelProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["call-scores", callId],
    queryFn: () => apiGetScores(callId),
    enabled: callStatus === "scored",
    staleTime: 30_000,
  });

  return (
    <div
      data-testid="scorecard-panel"
      className={cn(
        "flex flex-col overflow-auto rounded-lg border border-border bg-card",
        className,
      )}
    >
      {/* ── Panel header ── */}
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">
          Quality Scorecard
        </h3>
        {callStatus === "scored" && data && data.scores.length > 0 && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            {data.scores.length} dimension{data.scores.length !== 1 ? "s" : ""} scored
          </p>
        )}
      </div>

      {/* ── Body ── */}
      <div className="flex flex-col gap-3 p-4">
        {/* 1. Pre-scoring: call not yet processed */}
        {PRE_SCORING_STATUSES.has(callStatus) && (
          <div
            data-testid="scorecard-empty"
            className="flex flex-col items-center gap-3 py-10 text-center"
          >
            {/* Simple clock-like icon */}
            <svg
              aria-hidden="true"
              className="h-8 w-8 text-muted-foreground/40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v6l4 2" />
            </svg>
            <p className="text-sm text-muted-foreground">
              Scorecard will appear once the call is fully processed.
            </p>
          </div>
        )}

        {/* 2. Scoring in progress */}
        {callStatus === "scoring" && (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <div
              data-testid="scoring-spinner"
              aria-label="Scoring in progress"
              className={cn(
                "h-8 w-8 rounded-full border-2 border-primary/20 border-t-primary",
                "animate-spin",
              )}
            />
            <p className="text-sm text-muted-foreground">
              Scoring in progress…
            </p>
          </div>
        )}

        {/* 3. Data loading (TanStack Query) */}
        {callStatus === "scored" && isLoading && (
          <div className="flex flex-col gap-3">
            {/* Skeleton shimmer cards */}
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-28 animate-pulse rounded-lg bg-muted/60"
              />
            ))}
          </div>
        )}

        {/* 4. Error */}
        {callStatus === "scored" && isError && (
          <div className="rounded-md bg-[hsl(var(--fail)/0.06)] px-4 py-3 text-sm text-[hsl(var(--fail))]">
            Failed to load scorecard. Please refresh the page.
          </div>
        )}

        {/* 5. Failed call status */}
        {callStatus === "failed" && (
          <div
            data-testid="scorecard-empty"
            className="rounded-md bg-[hsl(var(--fail)/0.06)] px-4 py-3 text-sm text-[hsl(var(--fail))]"
          >
            This call failed to process — no scorecard is available.
          </div>
        )}

        {/* 6. Scored with data */}
        {callStatus === "scored" && !isLoading && !isError && data && (
          <>
            {data.scores.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No scores available for this call yet.
              </p>
            ) : (
              data.scores.map((score) => (
                <DimensionScoreCard
                  key={score.id}
                  scoreData={score}
                  segments={segments}
                  onEvidenceClick={onEvidenceClick}
                />
              ))
            )}
          </>
        )}
      </div>
    </div>
  );
}
