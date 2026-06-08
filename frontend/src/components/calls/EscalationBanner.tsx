"use client";

import { cn } from "@/lib/utils";

interface EscalationBannerProps {
  reason: string | null;
  className?: string;
}

/**
 * Prominent banner shown when the supervisor flagged a call for human review.
 * Renders nothing when the call is not escalated — callers should gate on
 * analysis.escalate_for_review before rendering this component.
 */
export function EscalationBanner({ reason, className }: EscalationBannerProps) {
  return (
    <div
      data-testid="escalation-banner"
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-lg border border-[hsl(var(--fail)/0.35)]",
        "bg-[hsl(var(--fail)/0.06)] px-4 py-3.5",
        className,
      )}
    >
      {/* Icon */}
      <svg
        aria-hidden="true"
        className="mt-0.5 h-5 w-5 shrink-0 text-[hsl(var(--fail))]"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>

      {/* Text */}
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-semibold text-[hsl(var(--fail))]">
          Flagged for human review
        </p>
        {reason && (
          <p className="text-sm text-[hsl(var(--fail)/0.85)]">{reason}</p>
        )}
      </div>
    </div>
  );
}
