"use client";

import { cn } from "@/lib/utils";

interface CardSkeletonProps {
  className?: string;
  /** Height of the skeleton block (Tailwind h-* class, default h-32). */
  height?: string;
  "data-testid"?: string;
}

/** Pulsing placeholder shown while a dashboard card's data is loading. */
export function CardSkeleton({
  className,
  height = "h-32",
  "data-testid": testId = "card-skeleton",
}: CardSkeletonProps) {
  return (
    <div
      data-testid={testId}
      className={cn(
        "animate-pulse rounded-lg border border-border bg-card",
        height,
        className,
      )}
    >
      <div className="flex h-full flex-col gap-3 p-4">
        <div className="h-3 w-24 rounded bg-muted" />
        <div className="h-8 w-16 rounded bg-muted" />
        <div className="mt-auto h-2 w-32 rounded bg-muted" />
      </div>
    </div>
  );
}
