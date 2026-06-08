import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mocks ──────────────────────────────────────────────────────────────
const {
  mockApiGetAgents,
  mockApiGetAgent,
  mockApiGetAgentPerformance,
  mockApiGetAgentCoaching,
  mockApiCreateCoachingNote,
  mockApiDeleteCoachingNote,
  mockApiGetTeamAnalytics,
  mockApiGetLeaderboard,
  mockApiListTeams,
} = vi.hoisted(() => ({
  mockApiGetAgents: vi.fn(),
  mockApiGetAgent: vi.fn(),
  mockApiGetAgentPerformance: vi.fn(),
  mockApiGetAgentCoaching: vi.fn(),
  mockApiCreateCoachingNote: vi.fn(),
  mockApiDeleteCoachingNote: vi.fn(),
  mockApiGetTeamAnalytics: vi.fn(),
  mockApiGetLeaderboard: vi.fn(),
  mockApiListTeams: vi.fn(),
}));

vi.mock("@/lib/api/agents", () => ({
  apiGetAgents: mockApiGetAgents,
  apiGetAgent: mockApiGetAgent,
  apiGetAgentPerformance: mockApiGetAgentPerformance,
  apiGetAgentCoaching: mockApiGetAgentCoaching,
  apiCreateCoachingNote: mockApiCreateCoachingNote,
  apiDeleteCoachingNote: mockApiDeleteCoachingNote,
}));

vi.mock("@/lib/api/teams", () => ({
  apiGetTeamAnalytics: mockApiGetTeamAnalytics,
}));

vi.mock("@/lib/api/analytics", () => ({
  apiGetLeaderboard: mockApiGetLeaderboard,
  apiListTeams: mockApiListTeams,
  apiGetOverview: vi.fn().mockResolvedValue({ calls_total: 0, calls_scored: 0, avg_overall_score: null, compliance_pass_rate: null, flagged_count: 0 }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/app/agents",
  useParams: () => ({ id: "agent-1" }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [k: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

// Recharts ResizeObserver shim
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

import { DimensionBreakdown } from "@/components/agents/DimensionBreakdown";
import { VsTeamCard } from "@/components/agents/VsTeamCard";
import { CoachingPanel } from "@/components/agents/CoachingPanel";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const AGENT_1 = {
  id: "agent-1",
  name: "Alice Johnson",
  team_id: "team-1",
  created_at: "2026-01-01T00:00:00Z",
  calls_scored: 25,
  avg_overall_score: 82,
};

const AGENT_2 = {
  id: "agent-2",
  name: "Bob Smith",
  team_id: "team-1",
  created_at: "2026-01-01T00:00:00Z",
  calls_scored: 18,
  avg_overall_score: 67,
};

const LEADERBOARD_ITEMS = [
  {
    agent_id: "agent-1",
    name: "Alice Johnson",
    team: "Alpha",
    calls_scored: 25,
    avg_overall_score: 82,
    compliance_pass_rate: 0.92,
    is_at_risk: false,
  },
  {
    agent_id: "agent-2",
    name: "Bob Smith",
    team: "Alpha",
    calls_scored: 18,
    avg_overall_score: 67,
    compliance_pass_rate: 0.75,
    is_at_risk: true,
  },
];

const PERFORMANCE = {
  calls_scored: 25,
  avg_overall_score: 82.0,
  trend: [
    { date: "2026-05-26", avg_overall_score: 79.0 },
    { date: "2026-06-02", avg_overall_score: 83.5 },
  ],
  dimension_breakdown: [
    { dimension_key: "sentiment", dimension_name: "Sentiment", avg_score: 85.0 },
    { dimension_key: "script", dimension_name: "Script", avg_score: 78.0 },
    { dimension_key: "compliance", dimension_name: "Compliance", avg_score: 90.0 },
  ],
  vs_team: { agent_avg: 82.0, team_avg: 74.5 },
};

const COACHING_NOTES = [
  {
    id: "note-1",
    agent_id: "agent-1",
    call_id: null,
    source: "auto" as const,
    note: "Agent needs to improve empathy.",
    created_at: "2026-06-01T10:00:00Z",
  },
  {
    id: "note-2",
    agent_id: "agent-1",
    call_id: null,
    source: "manual" as const,
    note: "Discussed script adherence.",
    created_at: "2026-06-02T11:00:00Z",
  },
];

const TEAM_ANALYTICS = {
  calls_scored: 43,
  avg_overall_score: 75.5,
  compliance_pass_rate: 0.84,
  score_distribution: { quality: 20, at_risk: 15, fail: 8 },
  agent_comparison: [
    { agent_id: "agent-1", name: "Alice Johnson", calls_scored: 25, avg_overall_score: 82.0 },
    { agent_id: "agent-2", name: "Bob Smith", calls_scored: 18, avg_overall_score: 67.0 },
  ],
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ─────────────────────────────────────────────────────────────────────────────
// DimensionBreakdown
// ─────────────────────────────────────────────────────────────────────────────

describe("DimensionBreakdown", () => {
  it("renders all dimension bars", () => {
    render(<DimensionBreakdown items={PERFORMANCE.dimension_breakdown} />);
    expect(screen.getByTestId("dimension-breakdown")).toBeInTheDocument();
    expect(screen.getByTestId("bar-sentiment")).toBeInTheDocument();
    expect(screen.getByTestId("bar-script")).toBeInTheDocument();
    expect(screen.getByTestId("bar-compliance")).toBeInTheDocument();
  });

  it("renders dimension names and scores", () => {
    render(<DimensionBreakdown items={PERFORMANCE.dimension_breakdown} />);
    expect(screen.getByText("Sentiment")).toBeInTheDocument();
    expect(screen.getByText("85.0")).toBeInTheDocument();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(screen.getByText("90.0")).toBeInTheDocument();
  });

  it("shows empty state when no items", () => {
    render(<DimensionBreakdown items={[]} />);
    expect(screen.getByTestId("dimension-empty")).toBeInTheDocument();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// VsTeamCard
// ─────────────────────────────────────────────────────────────────────────────

describe("VsTeamCard", () => {
  it("renders agent and team averages", () => {
    render(<VsTeamCard data={PERFORMANCE.vs_team} />);
    expect(screen.getByTestId("vs-agent-score")).toHaveTextContent("82.0");
    expect(screen.getByTestId("vs-team-score")).toHaveTextContent("74.5");
  });

  it("renders positive delta when agent > team", () => {
    render(<VsTeamCard data={{ agent_avg: 82, team_avg: 74.5 }} />);
    expect(screen.getByTestId("vs-delta")).toHaveTextContent("+7.5");
  });

  it("renders negative delta when agent < team", () => {
    render(<VsTeamCard data={{ agent_avg: 65, team_avg: 80 }} />);
    expect(screen.getByTestId("vs-delta")).toHaveTextContent("-15.0");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// CoachingPanel
// ─────────────────────────────────────────────────────────────────────────────

describe("CoachingPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders notes list", () => {
    withQuery(<CoachingPanel agentId="agent-1" notes={COACHING_NOTES} />);
    expect(screen.getByTestId("coaching-notes-list")).toBeInTheDocument();
    expect(screen.getByTestId("coaching-note-note-1")).toBeInTheDocument();
    expect(screen.getByTestId("coaching-note-note-2")).toBeInTheDocument();
  });

  it("shows AI badge for auto notes", () => {
    withQuery(<CoachingPanel agentId="agent-1" notes={COACHING_NOTES} />);
    expect(screen.getByTestId("note-auto-badge-note-1")).toBeInTheDocument();
  });

  it("shows delete button for manual notes but NOT for auto notes", () => {
    withQuery(<CoachingPanel agentId="agent-1" notes={COACHING_NOTES} />);
    // Manual note-2 has delete
    expect(screen.getByTestId("note-delete-note-2")).toBeInTheDocument();
    // Auto note-1 does NOT have delete
    expect(screen.queryByTestId("note-delete-note-1")).not.toBeInTheDocument();
  });

  it("calls apiCreateCoachingNote on submit", async () => {
    const user = userEvent.setup();
    mockApiCreateCoachingNote.mockResolvedValueOnce({
      id: "note-3",
      agent_id: "agent-1",
      call_id: null,
      source: "manual",
      note: "New note",
      created_at: new Date().toISOString(),
    });
    withQuery(<CoachingPanel agentId="agent-1" notes={[]} />);
    await user.type(screen.getByTestId("coaching-input"), "New note");
    await user.click(screen.getByTestId("coaching-submit"));
    expect(mockApiCreateCoachingNote).toHaveBeenCalledWith({
      agent_id: "agent-1",
      note: "New note",
    });
  });

  it("delete button shows confirm/cancel, confirm calls apiDeleteCoachingNote", async () => {
    const user = userEvent.setup();
    mockApiDeleteCoachingNote.mockResolvedValueOnce(undefined);
    const manualOnly = [COACHING_NOTES[1]]; // note-2 is manual
    withQuery(<CoachingPanel agentId="agent-1" notes={manualOnly} />);

    // Click delete → shows confirm
    await user.click(screen.getByTestId("note-delete-note-2"));
    expect(screen.getByTestId("note-delete-confirm-note-2")).toBeInTheDocument();

    // Confirm → calls apiDeleteCoachingNote
    await user.click(screen.getByTestId("note-delete-confirm-note-2"));
    expect(mockApiDeleteCoachingNote).toHaveBeenCalledWith("note-2");
  });

  it("delete cancel hides confirm dialog without deleting", async () => {
    const user = userEvent.setup();
    const manualOnly = [COACHING_NOTES[1]];
    withQuery(<CoachingPanel agentId="agent-1" notes={manualOnly} />);
    await user.click(screen.getByTestId("note-delete-note-2"));
    await user.click(screen.getByTestId("note-delete-cancel-note-2"));
    expect(screen.queryByTestId("note-delete-confirm-note-2")).not.toBeInTheDocument();
    expect(mockApiDeleteCoachingNote).not.toHaveBeenCalled();
  });

  it("shows empty state when no notes", () => {
    withQuery(<CoachingPanel agentId="agent-1" notes={[]} />);
    expect(screen.getByTestId("coaching-empty")).toBeInTheDocument();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Leaderboard page integration (via component imports)
// We test the table rendering using the leaderboard data directly
// ─────────────────────────────────────────────────────────────────────────────

describe("Leaderboard rows rendering", () => {
  it("renders leaderboard rows with band-colored scores", async () => {
    mockApiGetLeaderboard.mockResolvedValue({ items: LEADERBOARD_ITEMS });
    mockApiListTeams.mockResolvedValue({ items: [{ id: "team-1", name: "Alpha" }] });

    const { default: AgentsPage } = await import("@/app/app/agents/page");
    const { unmount } = withQuery(<AgentsPage />);
    const table = await screen.findByTestId("leaderboard-table");

    expect(within(table).getByTestId(`leaderboard-row-agent-1`)).toBeInTheDocument();
    expect(within(table).getByTestId(`leaderboard-row-agent-2`)).toBeInTheDocument();

    // At-risk badge for agent-2
    expect(within(table).getByTestId("at-risk-badge-agent-2")).toBeInTheDocument();
    // On-track badge for agent-1
    expect(within(table).getByTestId("quality-badge-agent-1")).toBeInTheDocument();

    unmount();
  });

  it("shows agent links in leaderboard rows", async () => {
    mockApiGetLeaderboard.mockResolvedValue({ items: LEADERBOARD_ITEMS });
    mockApiListTeams.mockResolvedValue({ items: [] });

    const { default: AgentsPage } = await import("@/app/app/agents/page");
    const { unmount } = withQuery(<AgentsPage />);
    await screen.findByTestId("leaderboard-table");

    const link = screen.getByTestId("agent-link-agent-1");
    expect(link).toHaveAttribute("href", "/app/agents/agent-1");
    unmount();
  });

  it("shows empty state when no agents", async () => {
    mockApiGetLeaderboard.mockResolvedValue({ items: [] });
    mockApiListTeams.mockResolvedValue({ items: [] });

    const { default: AgentsPage } = await import("@/app/app/agents/page");
    const { unmount } = withQuery(<AgentsPage />);
    expect(await screen.findByTestId("leaderboard-empty")).toBeInTheDocument();
    unmount();
  });

  it("re-queries leaderboard when filter changes", async () => {
    const user = userEvent.setup();
    mockApiGetLeaderboard.mockResolvedValue({ items: LEADERBOARD_ITEMS });
    mockApiListTeams.mockResolvedValue({
      items: [{ id: "team-1", name: "Alpha" }],
    });

    const { default: AgentsPage } = await import("@/app/app/agents/page");
    const { unmount } = withQuery(<AgentsPage />);
    await screen.findByTestId("leaderboard-table");

    // Click a preset to change date filter
    const preset = screen.getByTestId("preset-last-7-days");
    await user.click(preset);

    // apiGetLeaderboard called again (at least twice total)
    expect(mockApiGetLeaderboard.mock.calls.length).toBeGreaterThanOrEqual(2);
    unmount();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Team analytics page
// ─────────────────────────────────────────────────────────────────────────────

describe("Team analytics page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders team header stats", async () => {
    mockApiGetTeamAnalytics.mockResolvedValue(TEAM_ANALYTICS);
    mockApiListTeams.mockResolvedValue({
      items: [{ id: "team-1", name: "Alpha" }],
    });

    const { default: TeamDetailPage } = await import("@/app/app/teams/[id]/page");
    const { unmount } = withQuery(<TeamDetailPage />);

    expect(await screen.findByTestId("team-header")).toBeInTheDocument();
    expect(screen.getByTestId("team-calls-scored")).toHaveTextContent("43");
    expect(screen.getByTestId("team-avg-score")).toHaveTextContent("75.5");
    expect(screen.getByTestId("team-compliance")).toHaveTextContent("84%");
    unmount();
  });

  it("renders per-band distribution", async () => {
    mockApiGetTeamAnalytics.mockResolvedValue(TEAM_ANALYTICS);
    mockApiListTeams.mockResolvedValue({ items: [] });

    const { default: TeamDetailPage } = await import("@/app/app/teams/[id]/page");
    const { unmount } = withQuery(<TeamDetailPage />);

    expect(await screen.findByTestId("team-distribution")).toBeInTheDocument();
    expect(screen.getByTestId("dist-quality")).toBeInTheDocument();
    expect(screen.getByTestId("dist-at-risk")).toBeInTheDocument();
    expect(screen.getByTestId("dist-fail")).toBeInTheDocument();
    unmount();
  });

  it("renders agent comparison with links to agent detail", async () => {
    mockApiGetTeamAnalytics.mockResolvedValue(TEAM_ANALYTICS);
    mockApiListTeams.mockResolvedValue({ items: [] });

    const { default: TeamDetailPage } = await import("@/app/app/teams/[id]/page");
    const { unmount } = withQuery(<TeamDetailPage />);

    expect(await screen.findByTestId("agent-comparison")).toBeInTheDocument();
    const link = screen.getByTestId("agent-comparison-link-agent-1");
    expect(link).toHaveAttribute("href", "/app/agents/agent-1");
    unmount();
  });

  it("renders 404 state for unknown team", async () => {
    const { ApiError } = await import("@/lib/api/client");
    mockApiGetTeamAnalytics.mockRejectedValue(new ApiError(404, { error: "not_found" }));
    mockApiListTeams.mockResolvedValue({ items: [] });

    const { default: TeamDetailPage } = await import("@/app/app/teams/[id]/page");
    const { unmount } = withQuery(<TeamDetailPage />);

    expect(await screen.findByTestId("team-not-found")).toBeInTheDocument();
    unmount();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Agent detail page
// ─────────────────────────────────────────────────────────────────────────────

describe("Agent detail page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders trend, dimension breakdown, and vs-team from mocked payload", async () => {
    mockApiGetAgent.mockResolvedValue(AGENT_1);
    mockApiGetAgentPerformance.mockResolvedValue(PERFORMANCE);
    mockApiGetAgentCoaching.mockResolvedValue({ items: [], agent_id: "agent-1" });

    const { default: AgentDetailPage } = await import("@/app/app/agents/[id]/page");
    const { unmount } = withQuery(<AgentDetailPage />);

    expect(await screen.findByTestId("agent-header")).toBeInTheDocument();
    expect(screen.getByTestId("agent-name")).toHaveTextContent("Alice Johnson");
    expect(screen.getByTestId("agent-avg-score")).toHaveTextContent("82");
    expect(await screen.findByTestId("dimension-breakdown")).toBeInTheDocument();
    expect(await screen.findByTestId("vs-team-card")).toBeInTheDocument();
    unmount();
  });

  it("renders 404 state for unknown agent", async () => {
    const { ApiError } = await import("@/lib/api/client");
    mockApiGetAgent.mockRejectedValue(new ApiError(404, { error: "not_found" }));
    mockApiGetAgentPerformance.mockResolvedValue(PERFORMANCE);
    mockApiGetAgentCoaching.mockResolvedValue({ items: [], agent_id: "agent-1" });

    const { default: AgentDetailPage } = await import("@/app/app/agents/[id]/page");
    const { unmount } = withQuery(<AgentDetailPage />);

    expect(await screen.findByTestId("agent-not-found")).toBeInTheDocument();
    unmount();
  });
});
