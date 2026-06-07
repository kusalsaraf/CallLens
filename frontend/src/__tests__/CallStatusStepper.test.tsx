import { render, screen, act, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SsePayload } from "@/lib/api/calls";

// ── Hoist mock variables so vi.mock factory can reference them ────────────────
const { mockSubscribe, getCaptured } = vi.hoisted(() => {
  let capturedOnEvent: ((p: SsePayload) => void) | null = null;
  const mockSubscribe = vi.fn(
    (
      _id: string,
      onEvent: (p: SsePayload) => void,
      _sig: AbortSignal,
    ): Promise<void> => {
      capturedOnEvent = onEvent;
      return new Promise(() => {
        /* never resolves — test drives events manually */
      });
    },
  );
  return {
    mockSubscribe,
    getCaptured: () => capturedOnEvent,
  };
});

vi.mock("@/lib/api/calls", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/calls")>();
  return { ...actual, subscribeCallEvents: mockSubscribe };
});

import { CallStatusStepper } from "@/components/calls/CallStatusStepper";

// ── Helpers ───────────────────────────────────────────────────────────────────

function sendEvent(payload: SsePayload) {
  act(() => {
    getCaptured()?.(payload);
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockSubscribe.mockClear();
});
afterEach(() => vi.clearAllMocks());

describe("CallStatusStepper", () => {
  it("shows initial status immediately", () => {
    render(
      <CallStatusStepper callId="abc" initialStatus="transcribing" />,
    );
    expect(screen.getByText(/transcribing/i)).toBeInTheDocument();
  });

  it("advances status as SSE events arrive", async () => {
    render(<CallStatusStepper callId="abc" initialStatus="transcribing" />);

    sendEvent({ status: "diarizing" });
    await waitFor(() =>
      expect(screen.getByText(/diarizing/i)).toBeInTheDocument(),
    );
  });

  it("calls onComplete when transcribed event arrives", async () => {
    const onComplete = vi.fn();
    render(
      <CallStatusStepper
        callId="abc"
        initialStatus="transcribing"
        onComplete={onComplete}
      />,
    );

    sendEvent({ status: "transcribed" });
    await waitFor(() =>
      expect(onComplete).toHaveBeenCalledWith("transcribed"),
    );
  });

  it("shows error detail on failed event", async () => {
    render(<CallStatusStepper callId="abc" initialStatus="transcribing" />);

    sendEvent({ status: "failed", detail: "transcriber exploded" });
    await waitFor(() =>
      expect(screen.getByText(/transcriber exploded/i)).toBeInTheDocument(),
    );
  });

  it("does NOT subscribe when initial status is already terminal", () => {
    render(
      <CallStatusStepper callId="abc" initialStatus="transcribed" />,
    );
    expect(mockSubscribe).not.toHaveBeenCalled();
  });
});
