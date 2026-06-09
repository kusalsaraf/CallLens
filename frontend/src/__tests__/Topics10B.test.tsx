import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mocks ──────────────────────────────────────────────────────────────
const {
  mockApiGetTopicAnalytics,
  mockApiListTopics,
  mockApiListTeams,
  mockApiListCalls,
  mockApiGetCall,
  mockApiGetTranscript,
  mockApiGetAnalysis,
  mockApiGetTrace,
  mockFetchAudioObjectUrl,
} = vi.hoisted(() => ({
  mockApiGetTopicAnalytics: vi.fn(),
  mockApiListTopics: vi.fn(),
  mockApiListTeams: vi.fn(),
  mockApiListCalls: vi.fn(),
  mockApiGetCall: vi.fn(),
  mockApiGetTranscript: vi.fn(),
  mockApiGetAnalysis: vi.fn(),
  mockApiGetTrace: vi.fn(),
  mockFetchAudioObjectUrl: vi.fn(),
}));

vi.mock("@/lib/api/topics", () => ({
  apiGetTopicAnalytics: mockApiGetTopicAnalytics,
  apiListTopics: mockApiListTopics,
  apiGetTopic: vi.fn(),
}));

vi.mock("@/lib/api/analytics", () => ({
  apiListTeams: mockApiListTeams,
  apiGetOverview: vi.fn().mockResolvedValue({}),
  apiGetQualityTrends: vi.fn().mockResolvedValue({ bucket: "day", items: [] }),
  apiGetScoreDistribution: vi.fn().mockResolvedValue({ buckets: [], bands: { quality: 0, at_risk: 0, fail: 0 } }),
  apiGetCompliance: vi.fn().mockResolvedValue({ pass_rate: null, trend: [] }),
  apiGetFlagged: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 }),
  apiGetLeaderboard: vi.fn().mockResolvedValue({ items: [] }),
}));

vi.mock("@/lib/api/calls", () => ({
  apiListCalls: mockApiListCalls,
  apiGetCall: mockApiGetCall,
  apiGetTranscript: mockApiGetTranscript,
  apiGetAnalysis: mockApiGetAnalysis,
  apiGetTrace: mockApiGetTrace,
  apiDeleteCall: vi.fn(),
  apiGetScores: vi.fn().mockResolvedValue({ call_id: "", scores: [] }),
  fetchAudioObjectUrl: mockFetchAudioObjectUrl,
  isTerminalStatus: (s: string) => ["scored", "transcribed", "failed"].includes(s),
  TERMINAL_STATUSES: new Set(["scored", "transcribed", "failed"]),
}));

const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  useSearchParams: () => mockSearchParams,
  usePathname: () => "/app/topics",
  useParams: () => ({ id: "call-1" }),
}));

// Polyfills
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

if (!URL.createObjectURL) {
  URL.createObjectURL = vi.fn(() => "blob:fake");
}
if (!URL.revokeObjectURL) {
  URL.revokeObjectURL = vi.fn();
}

import TopicsPage from "@/app/app/topics/page";
import CallsPage from "@/app/app/calls/page";
import CallDetailPage from "@/app/app/calls/[id]/page";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const TOPIC_ANALYTICS = {
  items: [
    {
      topic_id: "t1",
      name: "Billing Dispute",
      slug: "billing_dispute",
      call_count: 25,
      avg_overall_score: 65.0,
      band: "at-risk",
      flagged_rate: 0.4,
    },
    {
      topic_id: "t2",
      name: "Technical Issue",
      slug: "technical_issue",
      call_count: 15,
      avg_overall_score: 82.0,
      band: "quality",
      flagged_rate: 0.1,
    },
    {
      topic_id: "t3",
      name: "Cancellation",
      slug: "cancellation_churn_risk",
      call_count: 10,
      avg_overall_score: 45.0,
      band: "fail",
      flagged_rate: 0.7,
    },
  ],
};

const TOPICS_LIST = {
  items: [
    { id: "t1", name: "Billing Dispute", slug: "billing_dispute", keywords: [] },
    { id: "t2", name: "Technical Issue", slug: "technical_issue", keywords: [] },
    { id: "t3", name: "Cancellation", slug: "cancellation_churn_risk", keywords: [] },
  ],
};

const TEAMS = {
  items: [
    { id: "team1", name: "Alpha" },
    { id: "team2", name: "Beta" },
  ],
};

const CALLS_LIST = {
  items: [
    {
      id: "c1",
      status: "scored",
      original_filename: "call1.wav",
      duration_seconds: 120,
      agent_id: "a1",
      status_detail: null,
      created_at: "2026-06-01T10:00:00Z",
      updated_at: "2026-06-01T10:05:00Z",
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
};

const ANALYSIS_WITH_TOPICS = {
  id: "an-1",
  call_id: "call-1",
  overall_score: 78,
  summary: "Test summary",
  key_moments: [],
  action_items: [],
  sentiment_overall: "mixed",
  talk_listen_ratio: 1.5,
  interruptions: 2,
  longest_monologue_ms: 18000,
  total_turns: 12,
  compliance_passed: true,
  escalate_for_review: false,
  escalation_reason: null,
  topics: [
    { topic_id: "t1", name: "Billing Dispute", slug: "billing_dispute", relevance: 0.8 },
    { topic_id: "t2", name: "Technical Issue", slug: "technical_issue", relevance: 0.5 },
  ],
  created_at: "2026-06-08T10:00:00Z",
};

const ANALYSIS_NO_TOPICS = {
  ...ANALYSIS_WITH_TOPICS,
  topics: [],
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function resetMocks() {
  mockReplace.mockReset();
  mockSearchParams = new URLSearchParams();
  mockApiGetTopicAnalytics.mockResolvedValue(TOPIC_ANALYTICS);
  mockApiListTopics.mockResolvedValue(TOPICS_LIST);
  mockApiListTeams.mockResolvedValue(TEAMS);
  mockApiListCalls.mockResolvedValue(CALLS_LIST);
  mockApiGetCall.mockResolvedValue({
    id: "call-1",
    status: "scored",
    original_filename: "call1.wav",
    duration_seconds: 120,
    agent_id: "a1",
    status_detail: null,
    created_at: "2026-06-01T10:00:00Z",
    updated_at: "2026-06-01T10:05:00Z",
  });
  mockApiGetTranscript.mockResolvedValue({
    id: "tr-1",
    call_id: "call-1",
    language: "en",
    redaction_provider: null,
    entities_redacted: null,
    segments: [
      { id: "seg-a", sequence: 0, start_ms: 0, end_ms: 3000, text: "Hello", redacted_text: null, speaker: "agent" },
    ],
    created_at: "2026-06-01T10:00:00Z",
  });
  mockApiGetAnalysis.mockResolvedValue(ANALYSIS_WITH_TOPICS);
  mockApiGetTrace.mockResolvedValue({ call_id: "call-1", runs: [] });
  mockFetchAudioObjectUrl.mockResolvedValue("blob:fake");
}

// ── Topics View ──────────────────────────────────────────────────────────────

describe("TopicsPage", () => {
  beforeEach(resetMocks);

  it("renders ranked rows with call_count and band-colored avg", async () => {
    withQuery(<TopicsPage />);
    const table = await screen.findByTestId("topics-table");
    expect(table).toBeInTheDocument();
    expect(within(table).getByText("Billing Dispute")).toBeInTheDocument();
    expect(within(table).getByText("25")).toBeInTheDocument();
    expect(within(table).getByText("65.0")).toBeInTheDocument();
  });

  it("renders flagged_rate as percentage", async () => {
    withQuery(<TopicsPage />);
    const table = await screen.findByTestId("topics-table");
    expect(within(table).getByText("40.0%")).toBeInTheDocument();
    expect(within(table).getByText("70.0%")).toBeInTheDocument();
  });

  it("topic row links to /app/calls?topic_id=...", async () => {
    withQuery(<TopicsPage />);
    const link = await screen.findByTestId("topic-link-billing_dispute");
    expect(link).toHaveAttribute("href", "/app/calls?topic_id=t1");
  });

  it("sorting by flagged_rate reorders rows", async () => {
    const user = userEvent.setup();
    withQuery(<TopicsPage />);
    await screen.findByTestId("topics-table");
    await user.click(screen.getByTestId("sort-flagged-rate"));

    const rows = screen.getAllByRole("row");
    // First data row (index 1, after header) should be highest flagged_rate
    expect(within(rows[1]).getByText("Cancellation")).toBeInTheDocument();
  });

  it("sorting by avg_overall_score works", async () => {
    const user = userEvent.setup();
    withQuery(<TopicsPage />);
    await screen.findByTestId("topics-table");
    await user.click(screen.getByTestId("sort-avg-score"));

    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByText("Technical Issue")).toBeInTheDocument();
  });

  it("renders the bar chart", async () => {
    withQuery(<TopicsPage />);
    const chart = await screen.findByTestId("topic-chart");
    expect(chart).toBeInTheDocument();
  });

  it("shows empty state when no topics", async () => {
    mockApiGetTopicAnalytics.mockResolvedValue({ items: [] });
    withQuery(<TopicsPage />);
    expect(await screen.findByText(/No topics found/)).toBeInTheDocument();
  });
});

// ── Calls List with Topic Filter ─────────────────────────────────────────────

describe("CallsPage with topic filter", () => {
  beforeEach(resetMocks);

  it("reads ?topic_id from URL and shows topic chip", async () => {
    mockSearchParams = new URLSearchParams("topic_id=t1");
    withQuery(<CallsPage />);
    const chip = await screen.findByTestId("topic-chip");
    expect(chip).toHaveTextContent("Topic: Billing Dispute");
  });

  it("clearing topic chip removes the param", async () => {
    mockSearchParams = new URLSearchParams("topic_id=t1");
    const user = userEvent.setup();
    withQuery(<CallsPage />);
    const clearBtn = await screen.findByTestId("topic-chip-clear");
    await user.click(clearBtn);
    expect(mockReplace).toHaveBeenCalledWith("/app/calls");
  });

  it("topic selector triggers a filtered query", async () => {
    const user = userEvent.setup();
    withQuery(<CallsPage />);
    const select = await screen.findByTestId("topic-selector");
    await user.selectOptions(select, "t2");
    expect(mockReplace).toHaveBeenCalledWith("/app/calls?topic_id=t2");
  });

  it("status filter still works alongside topic filter", async () => {
    mockSearchParams = new URLSearchParams("topic_id=t1");
    const user = userEvent.setup();
    withQuery(<CallsPage />);
    await screen.findByTestId("topic-chip");
    const statusSelect = screen.getByTestId("status-filter");
    await user.selectOptions(statusSelect, "failed");
    expect(mockApiListCalls).toHaveBeenCalledWith(
      expect.objectContaining({ status: "failed", topic_id: "t1" }),
    );
  });

  it("renders calls table normally without topic_id", async () => {
    withQuery(<CallsPage />);
    const filename = await screen.findByText("call1.wav");
    expect(filename).toBeInTheDocument();
  });
});

// ── Call Detail with Topic Chips ─────────────────────────────────────────────

describe("CallDetailPage topic chips", () => {
  beforeEach(resetMocks);

  it("renders topic chips linking to filtered calls list", async () => {
    withQuery(<CallDetailPage />);
    const chips = await screen.findByTestId("topic-chips");
    const links = within(chips).getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveTextContent("Billing Dispute");
    expect(links[0]).toHaveAttribute("href", "/app/calls?topic_id=t1");
    expect(links[1]).toHaveTextContent("Technical Issue");
    expect(links[1]).toHaveAttribute("href", "/app/calls?topic_id=t2");
  });

  it("renders nothing when topics array is empty", async () => {
    mockApiGetAnalysis.mockResolvedValue(ANALYSIS_NO_TOPICS);
    withQuery(<CallDetailPage />);
    await screen.findByText("call1.wav");
    expect(screen.queryByTestId("topic-chips")).not.toBeInTheDocument();
  });
});
