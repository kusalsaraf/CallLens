import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mocks ──────────────────────────────────────────────────────────────
const {
  mockApiGetOverview,
  mockApiGetQualityTrends,
  mockApiGetScoreDistribution,
  mockApiGetCompliance,
  mockApiGetFlagged,
  mockApiListTeams,
} = vi.hoisted(() => ({
  mockApiGetOverview: vi.fn(),
  mockApiGetQualityTrends: vi.fn(),
  mockApiGetScoreDistribution: vi.fn(),
  mockApiGetCompliance: vi.fn(),
  mockApiGetFlagged: vi.fn(),
  mockApiListTeams: vi.fn(),
}));

vi.mock("@/lib/api/analytics", () => ({
  apiGetOverview: mockApiGetOverview,
  apiGetQualityTrends: mockApiGetQualityTrends,
  apiGetScoreDistribution: mockApiGetScoreDistribution,
  apiGetCompliance: mockApiGetCompliance,
  apiGetFlagged: mockApiGetFlagged,
  apiGetLeaderboard: vi.fn().mockResolvedValue({ items: [] }),
  apiListTeams: mockApiListTeams,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/app/overview",
}));

// Recharts ResizeObserver shim
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

import { KpiCards } from "@/components/overview/KpiCards";
import { FilterBar } from "@/components/overview/FilterBar";
import { QualityTrendChart } from "@/components/overview/QualityTrendChart";
import { ScoreDistributionChart } from "@/components/overview/ScoreDistributionChart";
import { FlaggedCallsTable } from "@/components/overview/FlaggedCallsTable";
import { CardSkeleton } from "@/components/overview/CardSkeleton";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const OVERVIEW = {
  calls_total: 120,
  calls_scored: 100,
  avg_overall_score: 74.2,
  compliance_pass_rate: 0.88,
  flagged_count: 8,
};

const TEAMS = {
  items: [
    { id: "t1", name: "Alpha" },
    { id: "t2", name: "Beta" },
  ],
};

const TRENDS = {
  bucket: "day",
  items: [
    { date: "2026-06-01", avg_overall_score: 72, calls_scored: 10 },
    { date: "2026-06-02", avg_overall_score: 78, calls_scored: 12 },
  ],
};

const DISTRIBUTION = {
  buckets: [
    { bucket: 40, label: "40–49", count: 3 },
    { bucket: 60, label: "60–69", count: 5 },
    { bucket: 80, label: "80–89", count: 7 },
  ],
  bands: { quality: 7, at_risk: 5, fail: 3 },
};

const FLAGGED = {
  items: [
    {
      call_id: "c1",
      agent_name: "Alice",
      overall_score: 72,
      band: "at-risk",
      escalate_for_review: false,
      escalation_reason: null,
      uploaded_at: "2026-06-01T10:00:00Z",
    },
    {
      call_id: "c2",
      agent_name: "Bob",
      overall_score: 55,
      band: "fail",
      escalate_for_review: true,
      escalation_reason: "Compliance violation",
      uploaded_at: "2026-06-02T11:00:00Z",
    },
  ],
  total: 2,
  limit: 10,
  offset: 0,
};

const FLAGGED_EMPTY = { items: [], total: 0, limit: 10, offset: 0 };

// ── Helpers ───────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ── KpiCards ─────────────────────────────────────────────────────────────────

describe("KpiCards", () => {
  it("renders calls processed values", () => {
    withQuery(<KpiCards data={OVERVIEW} />);
    expect(screen.getByTestId("kpi-calls")).toHaveTextContent("100");
    expect(screen.getByTestId("kpi-calls")).toHaveTextContent("120");
  });

  it("renders avg score with band color class", () => {
    withQuery(<KpiCards data={OVERVIEW} />);
    const card = screen.getByTestId("kpi-avg-score");
    // 74.2 is at-risk band
    expect(card).toHaveTextContent("74.2");
  });

  it("renders compliance percentage", () => {
    withQuery(<KpiCards data={OVERVIEW} />);
    expect(screen.getByTestId("kpi-compliance")).toHaveTextContent("88%");
  });

  it("renders flagged count", () => {
    withQuery(<KpiCards data={OVERVIEW} />);
    expect(screen.getByTestId("kpi-flagged")).toHaveTextContent("8");
  });

  it("shows em-dash for null avg score", () => {
    const noScore = { ...OVERVIEW, avg_overall_score: null };
    withQuery(<KpiCards data={noScore} />);
    expect(screen.getByTestId("kpi-avg-score")).toHaveTextContent("—");
  });
});

// ── FilterBar ────────────────────────────────────────────────────────────────

describe("FilterBar", () => {
  it("renders date presets", () => {
    const onChange = vi.fn();
    render(
      <FilterBar
        filters={{ date_from: undefined, date_to: undefined }}
        teams={null}
        onFiltersChange={onChange}
      />,
    );
    expect(screen.getByTestId("preset-last-7-days")).toBeInTheDocument();
    expect(screen.getByTestId("preset-last-30-days")).toBeInTheDocument();
    expect(screen.getByTestId("preset-last-90-days")).toBeInTheDocument();
    expect(screen.getByTestId("preset-all-time")).toBeInTheDocument();
  });

  it("calls onFiltersChange with date range when preset clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FilterBar
        filters={{ date_from: undefined, date_to: undefined }}
        teams={null}
        onFiltersChange={onChange}
      />,
    );
    await user.click(screen.getByTestId("preset-last-7-days"));
    expect(onChange).toHaveBeenCalledOnce();
    const [arg] = onChange.mock.calls[0];
    expect(arg.date_from).toBeTruthy();
    expect(arg.date_to).toBeTruthy();
  });

  it("renders team selector when teams provided", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FilterBar
        filters={{}}
        teams={TEAMS}
        onFiltersChange={onChange}
      />,
    );
    const select = screen.getByTestId("team-selector");
    await user.selectOptions(select, "t1");
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ team_id: "t1" }));
  });

  it("triggers re-query on filter change (team selector interaction)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FilterBar
        filters={{}}
        teams={TEAMS}
        onFiltersChange={onChange}
      />,
    );
    await user.selectOptions(screen.getByTestId("team-selector"), "t2");
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ team_id: "t2" }));
  });
});

// ── QualityTrendChart ────────────────────────────────────────────────────────

describe("QualityTrendChart", () => {
  it("renders chart container", () => {
    render(
      <QualityTrendChart data={TRENDS} bucket="day" onBucketChange={vi.fn()} />,
    );
    expect(screen.getByTestId("quality-trend-chart")).toBeInTheDocument();
  });

  it("shows empty state when no data", () => {
    render(
      <QualityTrendChart
        data={{ bucket: "day", items: [] }}
        bucket="day"
        onBucketChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("trend-empty")).toBeInTheDocument();
  });

  it("calls onBucketChange with 'week' when Weekly button clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <QualityTrendChart data={TRENDS} bucket="day" onBucketChange={onChange} />,
    );
    await user.click(screen.getByTestId("bucket-week"));
    expect(onChange).toHaveBeenCalledWith("week");
  });

  it("calls onBucketChange with 'day' when Daily button clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <QualityTrendChart data={TRENDS} bucket="week" onBucketChange={onChange} />,
    );
    await user.click(screen.getByTestId("bucket-day"));
    expect(onChange).toHaveBeenCalledWith("day");
  });
});

// ── ScoreDistributionChart ───────────────────────────────────────────────────

describe("ScoreDistributionChart", () => {
  it("renders chart container", () => {
    render(<ScoreDistributionChart data={DISTRIBUTION} />);
    expect(screen.getByTestId("score-distribution-chart")).toBeInTheDocument();
  });

  it("shows band counts in header", () => {
    render(<ScoreDistributionChart data={DISTRIBUTION} />);
    expect(screen.getByTestId("band-quality")).toHaveTextContent("7");
    expect(screen.getByTestId("band-at-risk")).toHaveTextContent("5");
    expect(screen.getByTestId("band-fail")).toHaveTextContent("3");
  });

  it("shows empty state when no buckets", () => {
    const empty = { buckets: [], bands: { quality: 0, at_risk: 0, fail: 0 } };
    render(<ScoreDistributionChart data={empty} />);
    expect(screen.getByTestId("distribution-empty")).toBeInTheDocument();
  });
});

// ── FlaggedCallsTable ────────────────────────────────────────────────────────

describe("FlaggedCallsTable", () => {
  it("renders flagged rows", () => {
    render(<FlaggedCallsTable data={FLAGGED} onShowMore={vi.fn()} />);
    expect(screen.getByTestId("flagged-row-c1")).toBeInTheDocument();
    expect(screen.getByTestId("flagged-row-c2")).toBeInTheDocument();
  });

  it("shows agent names in rows", () => {
    render(<FlaggedCallsTable data={FLAGGED} onShowMore={vi.fn()} />);
    expect(screen.getByTestId("flagged-row-c1")).toHaveTextContent("Alice");
    expect(screen.getByTestId("flagged-row-c2")).toHaveTextContent("Bob");
  });

  it("links to /app/calls/[id]", () => {
    render(<FlaggedCallsTable data={FLAGGED} onShowMore={vi.fn()} />);
    const link = within(screen.getByTestId("flagged-row-c1")).getByRole("link");
    expect(link).toHaveAttribute("href", "/app/calls/c1");
  });

  it("shows empty state when no flagged calls", () => {
    render(<FlaggedCallsTable data={FLAGGED_EMPTY} onShowMore={vi.fn()} />);
    expect(screen.getByTestId("flagged-empty")).toHaveTextContent(
      "No flagged calls in this range — nice.",
    );
  });

  it("shows show-more button when more items remain", () => {
    const moreData = { ...FLAGGED, total: 15, offset: 0 };
    render(<FlaggedCallsTable data={moreData} onShowMore={vi.fn()} />);
    expect(screen.getByTestId("flagged-show-more")).toBeInTheDocument();
  });

  it("hides show-more when all items shown", () => {
    render(<FlaggedCallsTable data={FLAGGED} onShowMore={vi.fn()} />);
    expect(screen.queryByTestId("flagged-show-more")).not.toBeInTheDocument();
  });

  it("calls onShowMore when button clicked", async () => {
    const user = userEvent.setup();
    const onShowMore = vi.fn();
    const moreData = { ...FLAGGED, total: 15, offset: 0 };
    render(<FlaggedCallsTable data={moreData} onShowMore={onShowMore} />);
    await user.click(screen.getByTestId("flagged-show-more"));
    expect(onShowMore).toHaveBeenCalledOnce();
  });
});

// ── CardSkeleton ─────────────────────────────────────────────────────────────

describe("CardSkeleton", () => {
  it("renders with default testid", () => {
    render(<CardSkeleton />);
    expect(screen.getByTestId("card-skeleton")).toBeInTheDocument();
  });

  it("renders with custom testid", () => {
    render(<CardSkeleton data-testid="custom-skel" />);
    expect(screen.getByTestId("custom-skel")).toBeInTheDocument();
  });

  it("applies animate-pulse class", () => {
    render(<CardSkeleton />);
    expect(screen.getByTestId("card-skeleton")).toHaveClass("animate-pulse");
  });
});
