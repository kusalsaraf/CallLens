import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SegmentOut } from "@/lib/api/calls";
import { TranscriptPanel } from "@/components/calls/TranscriptPanel";

const SEGMENTS: SegmentOut[] = [
  {
    id: "s1",
    sequence: 0,
    start_ms: 0,
    end_ms: 4000,
    text: "Hello there",
    speaker: "agent",
  },
  {
    id: "s2",
    sequence: 1,
    start_ms: 4500,
    end_ms: 9000,
    text: "Hi how can I help",
    speaker: "customer",
  },
  {
    id: "s3",
    sequence: 2,
    start_ms: 9500,
    end_ms: 14000,
    text: "I have a question",
    speaker: "agent",
  },
];

describe("TranscriptPanel", () => {
  it("renders all segment texts", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );
    expect(screen.getByText("Hello there")).toBeInTheDocument();
    expect(screen.getByText("Hi how can I help")).toBeInTheDocument();
    expect(screen.getByText("I have a question")).toBeInTheDocument();
  });

  it("clicking a segment calls onSeek with the segment start_ms", async () => {
    const onSeek = vi.fn();
    const user = userEvent.setup();
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={0}
        onSeek={onSeek}
      />,
    );
    await user.click(screen.getByText("Hi how can I help"));
    expect(onSeek).toHaveBeenCalledWith(4500);
  });

  it("marks the active segment with data-active when currentTimeSec matches", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={5}  // 5s falls in segment 2 (4.5s–9s)
        onSeek={vi.fn()}
      />,
    );
    const activeEl = document.querySelector("[data-active]");
    expect(activeEl).not.toBeNull();
    expect(activeEl).toHaveTextContent("Hi how can I help");
  });

  it("shows no active segment when currentTimeSec is before the first segment", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={-1}
        onSeek={vi.fn()}
      />,
    );
    expect(document.querySelector("[data-active]")).toBeNull();
  });

  it("displays speaker labels visually distinguished", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );
    const agentLabels = screen.getAllByText("agent");
    const customerLabels = screen.getAllByText("customer");
    expect(agentLabels.length).toBeGreaterThan(0);
    expect(customerLabels.length).toBeGreaterThan(0);
  });

  it("shows empty-state message when segments array is empty", () => {
    render(
      <TranscriptPanel
        segments={[]}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );
    expect(screen.getByText(/no transcript/i)).toBeInTheDocument();
  });

  it("applies data-focused attribute to focused segment", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={0}
        onSeek={vi.fn()}
        focusedSegmentId="s2"
      />,
    );
    const focusedEl = document.querySelector("[data-focused]");
    expect(focusedEl).not.toBeNull();
    expect(focusedEl).toHaveTextContent("Hi how can I help");
  });

  it("no data-focused when focusedSegmentId is undefined", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );
    expect(document.querySelector("[data-focused]")).toBeNull();
  });
});
