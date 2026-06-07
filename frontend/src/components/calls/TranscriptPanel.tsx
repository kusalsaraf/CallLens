"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { SegmentOut } from "@/lib/api/calls";

interface TranscriptPanelProps {
  segments: SegmentOut[];
  currentTimeSec: number;
  onSeek: (ms: number) => void;
  className?: string;
  focusedSegmentId?: string;
  onFocusedSegmentChange?: (id: string | null) => void;
}

function formatMs(ms: number): string {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function TranscriptPanel({
  segments,
  currentTimeSec,
  onSeek,
  className,
  focusedSegmentId,
  onFocusedSegmentChange,
}: TranscriptPanelProps) {
  // Find the last segment whose start is <= currentTimeSec
  let activeIdx = -1;
  for (let i = 0; i < segments.length; i++) {
    if (segments[i].start_ms / 1000 <= currentTimeSec) {
      activeIdx = i;
    }
  }

  const activeRef = useRef<HTMLButtonElement | null>(null);
  const focusedRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    // scrollIntoView not available in jsdom; guard for test environments
    if (activeRef.current && typeof activeRef.current.scrollIntoView === "function") {
      activeRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeIdx]);

  useEffect(() => {
    if (
      focusedRef.current &&
      typeof focusedRef.current.scrollIntoView === "function"
    ) {
      focusedRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [focusedSegmentId]);

  if (segments.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center justify-center py-12 text-sm text-muted-foreground",
          className,
        )}
      >
        No transcript available yet.
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col overflow-auto rounded-lg border border-border bg-card",
        className,
      )}
    >
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">Transcript</h3>
      </div>

      <div className="flex flex-col p-2">
        {segments.map((seg, idx) => {
          const isActive = idx === activeIdx;
          const isFocused = seg.id === focusedSegmentId;

          return (
            <button
              key={seg.id}
              ref={isActive ? activeRef : isFocused ? focusedRef : null}
              data-active={isActive || undefined}
              data-focused={isFocused || undefined}
              onClick={() => onSeek(seg.start_ms)}
              className={cn(
                "flex gap-3 rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted/50",
                isActive && "bg-primary/5 ring-1 ring-inset ring-primary/20",
                isFocused && "animate-segment-flash",
              )}
            >
              {/* Timestamp */}
              <span className="tabular shrink-0 pt-0.5 text-[11px] text-muted-foreground">
                {formatMs(seg.start_ms)}
              </span>

              {/* Speaker + text */}
              <div className="flex flex-1 flex-col gap-0.5">
                <span
                  className={cn(
                    "text-[10px] font-bold uppercase tracking-wider",
                    seg.speaker === "agent" && "text-primary",
                    seg.speaker === "customer" &&
                      "text-[hsl(var(--at-risk))]",
                    seg.speaker === "unknown" && "text-muted-foreground",
                  )}
                >
                  {seg.speaker}
                </span>
                <p className="text-sm leading-relaxed text-foreground">
                  {seg.text}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
