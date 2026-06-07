"use client";

import { cn } from "@/lib/utils";

interface EvidenceChipProps {
  /** Verbatim transcript quote. */
  quote: string;
  /** Segment ID; may be null if the segment was deleted. */
  segmentId: string | null;
  /** Called when chip is clicked — only fires if segmentId is non-null. */
  onNavigate?: (segmentId: string) => void;
}

const MAX_QUOTE_LEN = 60;

/**
 * Compact pill that surfaces a single evidence quote and optionally scrolls
 * the transcript to the source segment when clicked.
 */
export function EvidenceChip({
  quote,
  segmentId,
  onNavigate,
}: EvidenceChipProps) {
  const isClickable = segmentId !== null && onNavigate !== undefined;
  const displayText =
    quote.length > MAX_QUOTE_LEN
      ? `${quote.slice(0, MAX_QUOTE_LEN)}…`
      : quote;

  function handleClick() {
    if (isClickable) {
      onNavigate!(segmentId!);
    }
  }

  return (
    <span
      data-testid="evidence-chip"
      title={quote}
      onClick={handleClick}
      role={isClickable ? "button" : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={
        isClickable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleClick();
              }
            }
          : undefined
      }
      className={cn(
        // Base chip
        "inline-flex items-center gap-1.5 rounded-md border-l-2 px-2 py-1",
        "text-xs leading-snug transition-colors",
        // Border accent in primary color
        "border-l-primary/50",
        // Background
        isClickable
          ? "bg-muted/60 hover:bg-muted cursor-pointer"
          : "bg-muted/40 opacity-70 cursor-default",
      )}
    >
      {/* Quote icon */}
      <svg
        aria-hidden="true"
        className="shrink-0 text-muted-foreground"
        width="10"
        height="10"
        viewBox="0 0 16 16"
        fill="currentColor"
      >
        <path d="M3.516 7c1.933 0 3.5 1.567 3.5 3.5S5.449 14 3.516 14 .016 12.433.016 10.5c0-.622.168-1.204.46-1.706L3.827 2h2.19L3.516 7zm9 0c1.933 0 3.5 1.567 3.5 3.5S14.449 14 12.516 14s-3.5-1.567-3.5-3.5c0-.622.168-1.204.46-1.706L12.827 2h2.19L12.516 7z" />
      </svg>

      <span className="text-foreground/80">{displayText}</span>
    </span>
  );
}
