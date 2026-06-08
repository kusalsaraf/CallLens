import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mocks ──────────────────────────────────────────────────────────────
const { mockApiGetScores, mockApiGetAnalysis, mockApiGetTrace } = vi.hoisted(
  () => ({
    mockApiGetScores: vi.fn(),
    mockApiGetAnalysis: vi.fn(),
    mockApiGetTrace: vi.fn(),
  }),
);

vi.mock("@/lib/api/calls", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/calls")>();
  return {
    ...actual,
    apiGetScores: mockApiGetScores,
    apiGetAnalysis: mockApiGetAnalysis,
    apiGetTrace: mockApiGetTrace,
  };
});

import { ScorecardPanel } from "@/components/calls/ScorecardPanel";
import { EscalationBanner } from "@/components/calls/EscalationBanner";
import { SummaryActionsCard } from "@/components/calls/SummaryActionsCard";
import { ConversationDynamics } from "@/components/calls/ConversationDynamics";
import { AgentRunTrace } from "@/components/calls/AgentRunTrace";

// ── Helpers ──────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ── Sample data ───────────────────────────────────────────────────────────────

const SEGMENT_A = {
  id: "seg-a",
  sequence: 0,
  start_ms: 1000,
  end_ms: 4000,
  text: "I understand your frustration completely.",
  speaker: "agent" as const,
};

const SEGMENT_B = {
  id: "seg-b",
  sequence: 1,
  start_ms: 4500,
  end_ms: 8000,
  text: "My account was charged twice.",
  speaker: "customer" as const,
};

const SAMPLE_SCORES = [
  {
    id: "s1",
    dimension: { id: "d1", key: "sentiment_empathy", name: "Sentiment & Empathy", weight: 0.25 },
    score: 92,
    confidence: 0.9,
    rationale: "Agent showed excellent empathy throughout.",
    is_supported: true,
    scored_at: "2026-06-08T10:00:00Z",
    evidence: [{ id: "e1", segment_id: "seg-a", quote: "I understand your frustration" }],
    band: "quality",
  },
  {
    id: "s2",
    dimension: { id: "d2", key: "compliance", name: "Compliance", weight: 0.2 },
    score: 55,
    confidence: 0.7,
    rationale: "Found: I understand. Missing: I apologize, Is there anything else.",
    is_supported: true,
    scored_at: "2026-06-08T10:00:00Z",
    evidence: [{ id: "e2", segment_id: "seg-a", quote: "I understand your frustration" }],
    band: "fail",
  },
];

const SAMPLE_ANALYSIS = {
  id: "an-1",
  call_id: "call-1",
  overall_score: 78,
  summary: "The agent handled the billing issue adequately but missed some required phrases.",
  key_moments: [
    { segment_id: "seg-a", label: "Agent empathy peak" },
    { segment_id: "seg-b", label: "Customer escalation" },
  ],
  action_items: ["Practice saying 'I apologize'", "Always close with 'Is there anything else'"],
  sentiment_overall: "mixed",
  talk_listen_ratio: 1.5,
  interruptions: 2,
  longest_monologue_ms: 18000,
  total_turns: 12,
  compliance_passed: false,
  escalate_for_review: false,
  escalation_reason: null,
  created_at: "2026-06-08T10:00:00Z",
};

const SAMPLE_TRACE = {
  call_id: "call-1",
  runs: [
    {
      id: "r1",
      node: "preprocess",
      role: "preprocess",
      provider: "internal",
      score: null,
      confidence: null,
      evidence_kept: 0,
      evidence_dropped: 0,
      duration_ms: 45,
      detail: null,
      created_at: "2026-06-08T10:00:00Z",
    },
    {
      id: "r2",
      node: "sentiment_empathy",
      role: "specialist",
      provider: "stub",
      score: 92,
      confidence: 0.9,
      evidence_kept: 3,
      evidence_dropped: 1,
      duration_ms: 312,
      detail: null,
      created_at: "2026-06-08T10:00:00Z",
    },
    {
      id: "r3",
      node: "compliance",
      role: "specialist",
      provider: "stub",
      score: 55,
      confidence: 0.7,
      evidence_kept: 1,
      evidence_dropped: 2,
      duration_ms: 289,
      detail: null,
      created_at: "2026-06-08T10:00:00Z",
    },
    {
      id: "r4",
      node: "supervisor",
      role: "supervisor",
      provider: "stub",
      score: 78,
      confidence: 0.85,
      evidence_kept: 0,
      evidence_dropped: 0,
      duration_ms: 198,
      detail: null,
      created_at: "2026-06-08T10:00:00Z",
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ── 1. Scorecard all dimensions + compliance ──────────────────────────────────

describe("ScorecardPanel — all dimensions with band colors and compliance", () => {
  it("renders all returned dimensions", async () => {
    mockApiGetScores.mockResolvedValue({ call_id: "call-1", scores: SAMPLE_SCORES });
    withQuery(
      <ScorecardPanel callId="call-1" callStatus="scored" segments={[SEGMENT_A, SEGMENT_B]} />,
    );
    await waitFor(() => {
      const cards = screen.getAllByTestId("dimension-score-card");
      expect(cards).toHaveLength(2);
    });
    expect(screen.getByText("Sentiment & Empathy")).toBeInTheDocument();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
  });

  it("shows 'Good' label for API band=quality", async () => {
    mockApiGetScores.mockResolvedValue({ call_id: "call-1", scores: [SAMPLE_SCORES[0]] });
    withQuery(
      <ScorecardPanel callId="call-1" callStatus="scored" segments={[SEGMENT_A]} />,
    );
    await waitFor(() => expect(screen.getByText("Good")).toBeInTheDocument());
  });

  it("shows 'Poor' label for API band=fail", async () => {
    mockApiGetScores.mockResolvedValue({ call_id: "call-1", scores: [SAMPLE_SCORES[1]] });
    withQuery(
      <ScorecardPanel callId="call-1" callStatus="scored" segments={[SEGMENT_A]} />,
    );
    await waitFor(() => expect(screen.getByText("Poor")).toBeInTheDocument());
  });

  it("renders compliance badge for the compliance dimension", async () => {
    mockApiGetScores.mockResolvedValue({ call_id: "call-1", scores: [SAMPLE_SCORES[1]] });
    withQuery(
      <ScorecardPanel callId="call-1" callStatus="scored" segments={[SEGMENT_A]} />,
    );
    await waitFor(() => expect(screen.getByTestId("compliance-badge")).toBeInTheDocument());
    expect(screen.getByText(/Required phrases missed/)).toBeInTheDocument();
  });

  it("shows scoring spinner when callStatus is scoring", () => {
    withQuery(
      <ScorecardPanel callId="call-1" callStatus="scoring" segments={[]} />,
    );
    expect(screen.getByTestId("scoring-spinner")).toBeInTheDocument();
  });

  it("shows empty state when callStatus is failed", () => {
    withQuery(
      <ScorecardPanel callId="call-1" callStatus="failed" segments={[]} />,
    );
    expect(screen.getByTestId("scorecard-empty")).toBeInTheDocument();
  });
});

// ── 2. Escalation banner ─────────────────────────────────────────────────────

describe("EscalationBanner", () => {
  it("renders the banner with reason text", () => {
    render(
      <EscalationBanner reason="Low compliance score and negative sentiment detected." />,
    );
    expect(screen.getByTestId("escalation-banner")).toBeInTheDocument();
    expect(screen.getByText(/Low compliance score/)).toBeInTheDocument();
    expect(screen.getByText("Flagged for human review")).toBeInTheDocument();
  });

  it("renders without reason when reason is null", () => {
    render(<EscalationBanner reason={null} />);
    expect(screen.getByTestId("escalation-banner")).toBeInTheDocument();
    expect(screen.getByText("Flagged for human review")).toBeInTheDocument();
  });
});

// ── 3. Key moment click seeks + sets focusedSegmentId ────────────────────────

describe("SummaryActionsCard — key moment click", () => {
  it("calls onMomentClick with segmentId and startMs when a key moment is clicked", async () => {
    const user = userEvent.setup();
    const onMomentClick = vi.fn();

    render(
      <SummaryActionsCard
        analysis={SAMPLE_ANALYSIS}
        segments={[SEGMENT_A, SEGMENT_B]}
        onMomentClick={onMomentClick}
      />,
    );

    const moments = screen.getAllByTestId("key-moment-item");
    expect(moments).toHaveLength(2);

    await user.click(moments[0]);
    expect(onMomentClick).toHaveBeenCalledWith("seg-a", 1000);
  });

  it("clicking second key moment uses correct segment start_ms", async () => {
    const user = userEvent.setup();
    const onMomentClick = vi.fn();

    render(
      <SummaryActionsCard
        analysis={SAMPLE_ANALYSIS}
        segments={[SEGMENT_A, SEGMENT_B]}
        onMomentClick={onMomentClick}
      />,
    );

    const moments = screen.getAllByTestId("key-moment-item");
    await user.click(moments[1]);
    expect(onMomentClick).toHaveBeenCalledWith("seg-b", 4500);
  });

  it("renders summary text", () => {
    render(
      <SummaryActionsCard analysis={SAMPLE_ANALYSIS} segments={[]} />,
    );
    expect(screen.getByText(/billing issue adequately/)).toBeInTheDocument();
  });

  it("renders action items", () => {
    render(
      <SummaryActionsCard analysis={SAMPLE_ANALYSIS} segments={[]} />,
    );
    expect(screen.getByText(/Practice saying 'I apologize'/)).toBeInTheDocument();
    expect(screen.getByText(/Is there anything else/)).toBeInTheDocument();
  });
});

// ── 4. Conversation dynamics ──────────────────────────────────────────────────

describe("ConversationDynamics", () => {
  it("renders the talk/listen split bar", () => {
    render(<ConversationDynamics analysis={SAMPLE_ANALYSIS} />);
    expect(screen.getByTestId("talk-listen-bar")).toBeInTheDocument();
  });

  it("renders interruption count", () => {
    render(<ConversationDynamics analysis={SAMPLE_ANALYSIS} />);
    expect(screen.getByTestId("interruptions-value")).toHaveTextContent("2");
  });

  it("renders longest monologue as MM:SS", () => {
    render(<ConversationDynamics analysis={SAMPLE_ANALYSIS} />);
    // 18000ms = 18s → 00:18
    expect(screen.getByTestId("monologue-value")).toHaveTextContent("00:18");
  });

  it("renders total turns", () => {
    render(<ConversationDynamics analysis={SAMPLE_ANALYSIS} />);
    expect(screen.getByTestId("turns-value")).toHaveTextContent("12");
  });
});

// ── 5. Agent run trace ────────────────────────────────────────────────────────

describe("AgentRunTrace", () => {
  async function openTrace() {
    const user = userEvent.setup();
    render(<AgentRunTrace trace={SAMPLE_TRACE} />);
    const toggle = screen.getByRole("button", { name: /How this score was made/i });
    await user.click(toggle);
  }

  it("renders trace section header", () => {
    render(<AgentRunTrace trace={SAMPLE_TRACE} />);
    expect(screen.getByTestId("agent-run-trace")).toBeInTheDocument();
    expect(screen.getByText(/How this score was made/)).toBeInTheDocument();
  });

  it("expands to show trace rows on click", async () => {
    await openTrace();
    const rows = screen.getAllByTestId("trace-row");
    expect(rows.length).toBeGreaterThanOrEqual(4);
  });

  it("shows preprocess, specialist, and supervisor rows after expand", async () => {
    await openTrace();
    expect(screen.getByText("Preprocess")).toBeInTheDocument();
    expect(screen.getByText("Sentiment & Empathy")).toBeInTheDocument();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(screen.getByText("Supervisor")).toBeInTheDocument();
  });

  it("shows provider for each run", async () => {
    await openTrace();
    const stubs = screen.getAllByText("stub");
    expect(stubs.length).toBeGreaterThan(0);
  });

  it("shows evidence kept/dropped for specialists", async () => {
    await openTrace();
    // specialist r2: 3 kept, 1 dropped
    expect(screen.getByText(/3 kept/)).toBeInTheDocument();
    expect(screen.getByText(/1 dropped/)).toBeInTheDocument();
  });
});

// ── 6. Failed and still-scoring states ───────────────────────────────────────

describe("Component states — failed and still-scoring", () => {
  it("ScorecardPanel renders failed state without crashing", () => {
    withQuery(
      <ScorecardPanel callId="call-1" callStatus="failed" segments={[]} />,
    );
    expect(screen.getByTestId("scorecard-empty")).toBeInTheDocument();
  });

  it("ScorecardPanel renders scoring spinner without crashing", () => {
    withQuery(
      <ScorecardPanel callId="call-1" callStatus="scoring" segments={[]} />,
    );
    expect(screen.getByTestId("scoring-spinner")).toBeInTheDocument();
  });

  it("ConversationDynamics renders with zero metrics without crashing", () => {
    const zeroAnalysis = {
      ...SAMPLE_ANALYSIS,
      talk_listen_ratio: 0,
      interruptions: 0,
      longest_monologue_ms: 0,
      total_turns: 0,
    };
    render(<ConversationDynamics analysis={zeroAnalysis} />);
    expect(screen.getByTestId("conversation-dynamics")).toBeInTheDocument();
    expect(screen.getByTestId("interruptions-value")).toHaveTextContent("0");
  });

  it("AgentRunTrace renders without crashing when trace has no runs", () => {
    render(<AgentRunTrace trace={{ call_id: "call-1", runs: [] }} />);
    expect(screen.getByTestId("agent-run-trace")).toBeInTheDocument();
  });
});
