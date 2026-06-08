"use client";

import { cn } from "@/lib/utils";
import {
  apiBandToScoreBand,
  BAND_LABEL,
  BAND_TEXT_CLASS,
} from "@/lib/constants/scoreBands";
import type { CallAnalysisOut } from "@/lib/api/calls";
import { formatDuration } from "@/lib/utils";

interface OverallScoreHeroProps {
  analysis: CallAnalysisOut;
  /** Call duration in seconds — shown next to the score. */
  durationSeconds: number | null;
  className?: string;
}

const CIRCUMFERENCE = 2 * Math.PI * 40; // r=40, viewBox 100×100

/**
 * Prominent hero block showing the supervisor's overall score as an SVG ring
 * gauge, the band label, and key call metadata.
 */
export function OverallScoreHero({
  analysis,
  durationSeconds,
  className,
}: OverallScoreHeroProps) {
  const band = apiBandToScoreBand(undefined, analysis.overall_score);
  const textClass = BAND_TEXT_CLASS[band];

  const strokeColor =
    band === "quality"
      ? "hsl(var(--quality))"
      : band === "at-risk"
        ? "hsl(var(--at-risk))"
        : "hsl(var(--fail))";

  const filled = (analysis.overall_score / 100) * CIRCUMFERENCE;
  const gap = CIRCUMFERENCE - filled;

  return (
    <div
      data-testid="overall-score-hero"
      className={cn(
        "flex items-center gap-6 rounded-xl border border-border bg-card p-5 shadow-sm",
        className,
      )}
    >
      {/* SVG ring gauge */}
      <div className="relative shrink-0" aria-hidden="true">
        <svg
          width="96"
          height="96"
          viewBox="0 0 100 100"
          className="-rotate-90"
        >
          {/* Track */}
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth="8"
          />
          {/* Progress arc */}
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke={strokeColor}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${gap}`}
            style={{ transition: "stroke-dasharray 0.6s ease" }}
          />
        </svg>
        {/* Score text centred over the ring */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            data-testid="overall-score-value"
            className={cn(
              "tabular text-2xl font-bold leading-none",
              textClass,
            )}
          >
            {analysis.overall_score}
          </span>
          <span className="text-[10px] font-medium text-muted-foreground">
            /100
          </span>
        </div>
      </div>

      {/* Text block */}
      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide",
              band === "quality"
                ? "bg-[hsl(var(--quality)/0.1)] text-[hsl(var(--quality))]"
                : band === "at-risk"
                  ? "bg-[hsl(var(--at-risk)/0.1)] text-[hsl(var(--at-risk))]"
                  : "bg-[hsl(var(--fail)/0.1)] text-[hsl(var(--fail))]",
            )}
          >
            {BAND_LABEL[band]}
          </span>
          {analysis.compliance_passed !== null && (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
                analysis.compliance_passed
                  ? "bg-[hsl(var(--quality)/0.08)] text-[hsl(var(--quality))]"
                  : "bg-[hsl(var(--fail)/0.08)] text-[hsl(var(--fail))]",
              )}
            >
              <span aria-hidden="true">
                {analysis.compliance_passed ? "✓" : "✗"}
              </span>
              Compliance {analysis.compliance_passed ? "passed" : "failed"}
            </span>
          )}
        </div>

        <p className="text-sm text-muted-foreground">Overall quality score</p>

        {durationSeconds != null && (
          <p className="tabular text-xs text-muted-foreground">
            Duration: {formatDuration(durationSeconds)}
          </p>
        )}
      </div>
    </div>
  );
}
