"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  scoreBand,
  BAND_LABEL,
  BAND_TEXT_CLASS,
  BAND_BG_CLASS,
  BAND_RING_CLASS,
} from "@/lib/constants/scoreBands";
import { EvidenceChip } from "./EvidenceChip";
import type { CallScoreOut, SegmentOut } from "@/lib/api/calls";

interface DimensionScoreCardProps {
  scoreData: CallScoreOut;
  /** All transcript segments — used to resolve evidence segment_ids to start_ms. */
  segments: SegmentOut[];
  onEvidenceClick?: (segmentId: string, startMs: number) => void;
}

const RATIONALE_PREVIEW_LEN = 80;

/** Build a lookup map from segment id → SegmentOut for O(1) resolution. */
function buildSegmentMap(segments: SegmentOut[]): Map<string, SegmentOut> {
  const map = new Map<string, SegmentOut>();
  for (const seg of segments) {
    map.set(seg.id, seg);
  }
  return map;
}

/**
 * Card displaying a single scored dimension: score ring, band badge,
 * confidence bar, optional unsupported warning, collapsible rationale,
 * and evidence chips.
 */
export function DimensionScoreCard({
  scoreData,
  segments,
  onEvidenceClick,
}: DimensionScoreCardProps) {
  const [rationaleOpen, setRationaleOpen] = useState(false);

  const band = scoreBand(scoreData.score);
  const bandLabel = BAND_LABEL[band];
  const textClass = BAND_TEXT_CLASS[band];
  const bgClass = BAND_BG_CLASS[band];
  const ringClass = BAND_RING_CLASS[band];

  const confidencePct = Math.round(scoreData.confidence * 100);
  const rationalePreview =
    scoreData.rationale.length > RATIONALE_PREVIEW_LEN
      ? `${scoreData.rationale.slice(0, RATIONALE_PREVIEW_LEN)}…`
      : scoreData.rationale;
  const hasFullRationale = scoreData.rationale.length > RATIONALE_PREVIEW_LEN;

  const segmentMap = buildSegmentMap(segments);

  function handleEvidenceNavigate(segmentId: string) {
    const seg = segmentMap.get(segmentId);
    if (seg && onEvidenceClick) {
      onEvidenceClick(segmentId, seg.start_ms);
    }
  }

  return (
    <div
      data-testid="dimension-score-card"
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-border bg-card p-4 shadow-sm",
      )}
    >
      {/* ── Header: score ring + name + band + confidence ── */}
      <div className="flex items-start gap-4">
        {/* Score ring */}
        <div
          className={cn(
            "relative flex h-12 w-12 shrink-0 items-center justify-center rounded-full ring-2",
            bgClass,
            ringClass,
          )}
        >
          <span
            data-testid="score-value"
            className={cn(
              "tabular text-base font-bold leading-none",
              textClass,
            )}
          >
            {scoreData.score}
          </span>
        </div>

        {/* Name, band badge, confidence */}
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-foreground leading-tight">
              {scoreData.dimension.name}
            </h3>

            {/* Band badge */}
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                bgClass,
                textClass,
              )}
            >
              {bandLabel}
            </span>

            {/* Low confidence qualifier when unsupported */}
            {!scoreData.is_supported && (
              <span className="text-[10px] text-muted-foreground italic">
                (low confidence)
              </span>
            )}
          </div>

          {/* Confidence bar */}
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  band === "quality"
                    ? "bg-[hsl(var(--quality))]"
                    : band === "at-risk"
                      ? "bg-[hsl(var(--at-risk))]"
                      : "bg-[hsl(var(--fail))]",
                )}
                style={{ width: `${confidencePct}%` }}
              />
            </div>
            <span className="shrink-0 text-[11px] tabular text-muted-foreground">
              {confidencePct}% confidence
            </span>
          </div>
        </div>
      </div>

      {/* ── Unsupported warning ── */}
      {!scoreData.is_supported && (
        <div
          data-testid="unsupported-indicator"
          className="flex items-start gap-2 rounded-md border border-[hsl(var(--at-risk)/0.3)] bg-[hsl(var(--at-risk)/0.06)] px-3 py-2.5 text-xs text-[hsl(var(--at-risk))]"
        >
          <span className="mt-px shrink-0" aria-hidden="true">
            ⚠
          </span>
          <span>
            Insufficient evidence — this score could not be verified against
            the transcript.
          </span>
        </div>
      )}

      {/* ── Rationale (collapsible) ── */}
      <div className="flex flex-col gap-1">
        <button
          data-testid="rationale-toggle"
          type="button"
          onClick={() => setRationaleOpen((v) => !v)}
          className="flex w-full items-center gap-1.5 text-left text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          aria-expanded={rationaleOpen}
        >
          {/* Chevron icon — no external library */}
          <svg
            aria-hidden="true"
            className={cn(
              "h-3 w-3 shrink-0 transition-transform duration-200",
              rationaleOpen && "rotate-90",
            )}
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M6 4l4 4-4 4" />
          </svg>
          Rationale
        </button>

        <p
          data-testid="rationale-text"
          className="text-xs leading-relaxed text-foreground/80"
        >
          {rationaleOpen || !hasFullRationale
            ? scoreData.rationale
            : rationalePreview}
        </p>
      </div>

      {/* ── Evidence chips ── */}
      {scoreData.evidence.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Evidence
          </span>
          <div className="flex flex-wrap gap-1.5">
            {scoreData.evidence.map((ev) => {
              const seg = ev.segment_id ? segmentMap.get(ev.segment_id) : null;
              return (
                <EvidenceChip
                  key={ev.id}
                  quote={ev.quote}
                  segmentId={seg ? seg.id : null}
                  onNavigate={
                    onEvidenceClick ? handleEvidenceNavigate : undefined
                  }
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
