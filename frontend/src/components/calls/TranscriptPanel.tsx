"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { SegmentOut } from "@/lib/api/calls";

interface TranscriptPanelProps {
  segments: SegmentOut[];
  currentTimeSec: number;
  onSeek: (ms: number) => void;
  className?: string;
  focusedSegmentId?: string;
  entitiesRedacted?: Record<string, number> | null;
  redactionProvider?: string | null;
}

const ENTITY_LABELS: Record<string, string> = {
  EMAIL: "email",
  PHONE: "phone",
  CARD: "card",
  SSN: "SSN",
  IP: "IP",
  PERSON: "name",
  LOCATION: "location",
  DATE: "date",
};

function formatMs(ms: number): string {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function PiiIndicator({ entities }: { entities: Record<string, number> }) {
  const parts = Object.entries(entities)
    .filter(([, count]) => count > 0)
    .map(([type, count]) => `${count} ${ENTITY_LABELS[type] ?? type.toLowerCase()}`);

  if (parts.length === 0) return null;

  return (
    <span
      data-testid="pii-indicator"
      className="rounded-md bg-[hsl(var(--at-risk)/0.08)] px-2 py-0.5 text-[10px] font-medium text-[hsl(var(--at-risk))]"
    >
      PII redacted: {parts.join(", ")}
    </span>
  );
}

export function TranscriptPanel({
  segments,
  currentTimeSec,
  onSeek,
  className,
  focusedSegmentId,
  entitiesRedacted,
  redactionProvider,
}: TranscriptPanelProps) {
  const [showOriginal, setShowOriginal] = useState(false);

  const hasRedaction = segments.some((s) => s.redacted_text != null);

  let activeIdx = -1;
  for (let i = 0; i < segments.length; i++) {
    if (segments[i].start_ms / 1000 <= currentTimeSec) {
      activeIdx = i;
    }
  }

  const activeRef = useRef<HTMLButtonElement | null>(null);
  const focusedRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
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
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground">Transcript</h3>
          {entitiesRedacted && Object.keys(entitiesRedacted).length > 0 ? (
            <PiiIndicator entities={entitiesRedacted} />
          ) : redactionProvider ? (
            <span data-testid="no-pii" className="text-[10px] text-muted-foreground">
              No PII detected
            </span>
          ) : null}
        </div>

        {hasRedaction && (
          <button
            data-testid="redaction-toggle"
            onClick={() => setShowOriginal((prev) => !prev)}
            className={cn(
              "rounded-md px-2 py-1 text-[10px] font-medium transition-colors",
              showOriginal
                ? "bg-[hsl(var(--at-risk)/0.1)] text-[hsl(var(--at-risk))]"
                : "bg-muted text-muted-foreground hover:text-foreground",
            )}
          >
            {showOriginal ? "Show redacted" : "Show original"}
          </button>
        )}
      </div>

      {showOriginal && (
        <div data-testid="original-notice" className="border-b border-border/50 bg-[hsl(var(--at-risk)/0.04)] px-4 py-1.5">
          <p className="text-[10px] text-[hsl(var(--at-risk))]">
            Showing unredacted transcript
          </p>
        </div>
      )}

      <div className="flex flex-col p-2">
        {segments.map((seg, idx) => {
          const isActive = idx === activeIdx;
          const isFocused = seg.id === focusedSegmentId;

          const displayText =
            showOriginal || !seg.redacted_text ? seg.text : seg.redacted_text;

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
              <span className="tabular shrink-0 pt-0.5 text-[11px] text-muted-foreground">
                {formatMs(seg.start_ms)}
              </span>

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
                <p data-testid="segment-text" className="text-sm leading-relaxed text-foreground">
                  {displayText}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
