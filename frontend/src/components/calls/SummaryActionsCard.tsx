"use client";

import { cn } from "@/lib/utils";
import type { CallAnalysisOut, SegmentOut } from "@/lib/api/calls";

interface SummaryActionsCardProps {
  analysis: CallAnalysisOut;
  segments: SegmentOut[];
  /** Called when a key moment is clicked — seeks audio and highlights transcript. */
  onMomentClick?: (segmentId: string, startMs: number) => void;
  className?: string;
}

function buildSegmentMap(segs: SegmentOut[]) {
  const m = new Map<string, SegmentOut>();
  for (const s of segs) m.set(s.id, s);
  return m;
}

/**
 * Card showing the supervisor's summary narrative, clickable key moments
 * (seek + flash), and action items as a display checklist.
 */
export function SummaryActionsCard({
  analysis,
  segments,
  onMomentClick,
  className,
}: SummaryActionsCardProps) {
  const segMap = buildSegmentMap(segments);

  function handleMomentClick(segmentId: string) {
    const seg = segMap.get(segmentId);
    if (seg && onMomentClick) {
      onMomentClick(segmentId, seg.start_ms);
    }
  }

  return (
    <div
      data-testid="summary-actions-card"
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-border bg-card p-4 shadow-sm",
        className,
      )}
    >
      {/* ── Summary ── */}
      <div className="flex flex-col gap-1.5">
        <h3 className="text-sm font-semibold text-foreground">Call Summary</h3>
        <p className="text-sm leading-relaxed text-foreground/80">
          {analysis.summary}
        </p>
      </div>

      {/* ── Key moments ── */}
      {analysis.key_moments.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Key Moments
          </h4>
          <ul className="flex flex-col gap-1.5">
            {analysis.key_moments.map((km, i) => {
              const seg = segMap.get(km.segment_id);
              const clickable = !!seg && !!onMomentClick;
              return (
                <li key={i}>
                  <button
                    type="button"
                    data-testid="key-moment-item"
                    disabled={!clickable}
                    onClick={clickable ? () => handleMomentClick(km.segment_id) : undefined}
                    className={cn(
                      "flex w-full items-start gap-2 rounded-md border-l-2 border-l-primary/40",
                      "bg-muted/40 px-3 py-2 text-left text-xs leading-snug transition-colors",
                      clickable
                        ? "cursor-pointer hover:bg-muted hover:border-l-primary"
                        : "cursor-default opacity-70",
                    )}
                  >
                    <svg
                      aria-hidden="true"
                      className="mt-px h-3 w-3 shrink-0 text-primary/60"
                      viewBox="0 0 16 16"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="8" cy="8" r="6" />
                      <path d="M8 5v3l2 1" />
                    </svg>
                    <span className="text-foreground/80">{km.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* ── Action items ── */}
      {analysis.action_items.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Recommended Actions
          </h4>
          <ul className="flex flex-col gap-1.5">
            {analysis.action_items.map((item, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm text-foreground/80"
              >
                <span
                  aria-hidden="true"
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-border text-[10px] text-muted-foreground"
                >
                  {i + 1}
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
