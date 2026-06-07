"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  type CallStatus,
  type SsePayload,
  isTerminalStatus,
  subscribeCallEvents,
} from "@/lib/api/calls";

const STEPS: CallStatus[] = [
  "uploaded",
  "transcribing",
  "diarizing",
  "transcribed",
];

interface CallStatusStepperProps {
  callId: string;
  initialStatus: CallStatus;
  onComplete?: (status: CallStatus) => void;
  className?: string;
}

export function CallStatusStepper({
  callId,
  initialStatus,
  onComplete,
  className,
}: CallStatusStepperProps) {
  const [status, setStatus] = useState<CallStatus>(initialStatus);
  const [detail, setDetail] = useState<string | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const handleEvent = useCallback((payload: SsePayload) => {
    const next = payload.status as CallStatus;
    setStatus(next);
    if (payload.detail) setDetail(payload.detail);
    if (isTerminalStatus(next)) {
      onCompleteRef.current?.(next);
    }
  }, []);

  useEffect(() => {
    if (isTerminalStatus(initialStatus)) {
      onCompleteRef.current?.(initialStatus);
      return;
    }
    const controller = new AbortController();
    void subscribeCallEvents(callId, handleEvent, controller.signal).catch(
      (e: unknown) => {
        if (e instanceof Error && e.name !== "AbortError") {
          console.error("SSE connection error", e);
        }
      },
    );
    return () => controller.abort();
  }, [callId, handleEvent, initialStatus]);

  const currentIdx = STEPS.indexOf(status === "failed" ? "transcribed" : status);
  const failed = status === "failed";

  return (
    <div className={cn("flex flex-col gap-4 rounded-lg border border-border bg-card p-6", className)}>
      <p className="text-sm font-medium text-foreground">
        {failed ? "Processing failed" : "Processing your recording…"}
      </p>

      {/* Step indicators */}
      <ol className="flex items-center gap-0">
        {STEPS.map((step, idx) => {
          const done = !failed && idx < currentIdx;
          const active = !failed && idx === currentIdx;
          const isFailed = failed && idx === currentIdx;

          return (
            <li key={step} className="flex flex-1 items-center">
              {/* Circle */}
              <div
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-colors",
                  done && "bg-[hsl(var(--quality))] text-white",
                  active && "animate-pulse-slow bg-primary text-primary-foreground",
                  isFailed && "bg-[hsl(var(--fail))] text-white",
                  !done && !active && !isFailed && "bg-muted text-muted-foreground",
                )}
                aria-current={active ? "step" : undefined}
              >
                {done ? "✓" : idx + 1}
              </div>
              {/* Label */}
              <span
                className={cn(
                  "ml-2 hidden text-xs font-medium sm:block",
                  (done || active) && !isFailed ? "text-foreground" : "text-muted-foreground",
                  isFailed && "text-[hsl(var(--fail))]",
                )}
              >
                {step}
              </span>
              {/* Connector */}
              {idx < STEPS.length - 1 && (
                <div
                  className={cn(
                    "mx-2 h-px flex-1 transition-colors",
                    done ? "bg-[hsl(var(--quality))]" : "bg-border",
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>

      {/* Error detail */}
      {failed && detail && (
        <p className="rounded-md bg-[hsl(var(--fail)/0.08)] px-3 py-2 text-xs text-[hsl(var(--fail))]">
          {detail}
        </p>
      )}
    </div>
  );
}
