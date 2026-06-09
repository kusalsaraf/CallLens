import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mock so vi.mock factory can reference it ────────────────────────────
const { mockApiGetScores } = vi.hoisted(() => {
  const mockApiGetScores = vi.fn();
  return { mockApiGetScores };
});

vi.mock("@/lib/api/calls", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/calls")>();
  return { ...actual, apiGetScores: mockApiGetScores };
});

import { EvidenceChip } from "@/components/calls/EvidenceChip";
import { DimensionScoreCard } from "@/components/calls/DimensionScoreCard";
import { ScorecardPanel } from "@/components/calls/ScorecardPanel";

// ── QueryClient wrapper ───────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ── Sample data ───────────────────────────────────────────────────────────────

const SAMPLE_SEGMENT = {
  id: "seg-1",
  sequence: 0,
  start_ms: 5000,
  end_ms: 9000,
  text: "Thank you for calling, how can I help you today?",
  redacted_text: null,
  speaker: "agent" as const,
};

const SAMPLE_SCORE = {
  id: "score-1",
  dimension: {
    id: "dim-1",
    key: "sentiment_empathy",
    name: "Sentiment & Empathy",
    weight: 0.25,
  },
  score: 85,
  confidence: 0.8,
  rationale:
    "The agent demonstrated excellent empathy throughout the call, using warm language and acknowledging the customer's frustration effectively.",
  is_supported: true,
  scored_at: "2026-06-07T12:00:00Z",
  evidence: [{ id: "ev-1", segment_id: "seg-1", quote: "Thank you for calling" }],
};

const UNSUPPORTED_SCORE = {
  ...SAMPLE_SCORE,
  id: "score-2",
  score: 45,
  confidence: 0.2,
  is_supported: false,
  evidence: [],
};

// ── Setup ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
});

// ── EvidenceChip ─────────────────────────────────────────────────────────────

describe("EvidenceChip", () => {
  it("renders quote text (possibly truncated)", () => {
    render(
      <EvidenceChip
        quote="Thank you for calling"
        segmentId="seg-1"
      />,
    );
    expect(screen.getByText(/Thank you for calling/)).toBeInTheDocument();
  });

  it("clicking chip calls onNavigate with segmentId", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(
      <EvidenceChip
        quote="Thank you for calling"
        segmentId="seg-1"
        onNavigate={onNavigate}
      />,
    );
    await user.click(screen.getByTestId("evidence-chip"));
    expect(onNavigate).toHaveBeenCalledWith("seg-1");
  });

  it("does not call onNavigate when segmentId is null", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(
      <EvidenceChip
        quote="Thank you for calling"
        segmentId={null}
        onNavigate={onNavigate}
      />,
    );
    await user.click(screen.getByTestId("evidence-chip"));
    expect(onNavigate).not.toHaveBeenCalled();
  });
});

// ── DimensionScoreCard ────────────────────────────────────────────────────────

describe("DimensionScoreCard", () => {
  it("renders score value", () => {
    render(
      <DimensionScoreCard
        scoreData={SAMPLE_SCORE}
        segments={[SAMPLE_SEGMENT]}
      />,
    );
    expect(screen.getByTestId("score-value")).toHaveTextContent("85");
  });

  it("score in quality band (>=80) shows 'Good' label", () => {
    render(
      <DimensionScoreCard
        scoreData={{ ...SAMPLE_SCORE, score: 85 }}
        segments={[]}
      />,
    );
    expect(screen.getByText("Good")).toBeInTheDocument();
  });

  it("score in at-risk band (60-79) shows 'At Risk' label", () => {
    render(
      <DimensionScoreCard
        scoreData={{ ...SAMPLE_SCORE, score: 65 }}
        segments={[]}
      />,
    );
    expect(screen.getByText("At Risk")).toBeInTheDocument();
  });

  it("score in fail band (<60) shows 'Poor' label", () => {
    render(
      <DimensionScoreCard
        scoreData={{ ...SAMPLE_SCORE, score: 45 }}
        segments={[]}
      />,
    );
    expect(screen.getByText("Poor")).toBeInTheDocument();
  });

  it("rationale expands on button click", async () => {
    const user = userEvent.setup();
    // SAMPLE_SCORE rationale is > 80 chars, so it starts truncated
    render(
      <DimensionScoreCard
        scoreData={SAMPLE_SCORE}
        segments={[SAMPLE_SEGMENT]}
      />,
    );
    const toggle = screen.getByTestId("rationale-toggle");
    await user.click(toggle);
    expect(screen.getByTestId("rationale-text")).toHaveTextContent(
      SAMPLE_SCORE.rationale,
    );
  });

  it("unsupported score shows unsupported-indicator", () => {
    render(
      <DimensionScoreCard scoreData={UNSUPPORTED_SCORE} segments={[]} />,
    );
    expect(screen.getByTestId("unsupported-indicator")).toBeInTheDocument();
  });

  it("evidence chips rendered for each evidence item", () => {
    render(
      <DimensionScoreCard
        scoreData={SAMPLE_SCORE}
        segments={[SAMPLE_SEGMENT]}
      />,
    );
    const chips = screen.getAllByTestId("evidence-chip");
    expect(chips).toHaveLength(1);
  });

  it("clicking evidence chip calls onEvidenceClick with segmentId and startMs", async () => {
    const user = userEvent.setup();
    const onEvidenceClick = vi.fn();
    render(
      <DimensionScoreCard
        scoreData={SAMPLE_SCORE}
        segments={[SAMPLE_SEGMENT]}
        onEvidenceClick={onEvidenceClick}
      />,
    );
    await user.click(screen.getByTestId("evidence-chip"));
    expect(onEvidenceClick).toHaveBeenCalledWith("seg-1", 5000);
  });
});

// ── ScorecardPanel ────────────────────────────────────────────────────────────

describe("ScorecardPanel", () => {
  it("shows empty state when callStatus is 'transcribed'", () => {
    withQuery(
      <ScorecardPanel
        callId="call-1"
        callStatus="transcribed"
        segments={[]}
      />,
    );
    expect(screen.getByTestId("scorecard-empty")).toBeInTheDocument();
  });

  it("shows scoring spinner when callStatus is 'scoring'", () => {
    withQuery(
      <ScorecardPanel
        callId="call-1"
        callStatus="scoring"
        segments={[]}
      />,
    );
    expect(screen.getByTestId("scoring-spinner")).toBeInTheDocument();
  });

  it("shows scores when callStatus is 'scored' and data loads", async () => {
    mockApiGetScores.mockResolvedValue({
      call_id: "call-1",
      scores: [SAMPLE_SCORE],
    });

    withQuery(
      <ScorecardPanel
        callId="call-1"
        callStatus="scored"
        segments={[SAMPLE_SEGMENT]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("dimension-score-card")).toBeInTheDocument();
    });

    expect(screen.getByTestId("score-value")).toHaveTextContent("85");
    expect(mockApiGetScores).toHaveBeenCalledWith("call-1");
  });
});
