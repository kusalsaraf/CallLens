import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mocks ──────────────────────────────────────────────────────────────

const { mockApiSearch, mockApiListTeams, mockPush, mockSearchParams } =
  vi.hoisted(() => ({
    mockApiSearch: vi.fn(),
    mockApiListTeams: vi.fn(),
    mockPush: vi.fn(),
    mockSearchParams: { get: vi.fn().mockReturnValue(null), toString: vi.fn().mockReturnValue("") },
  }));

vi.mock("@/lib/api/search", () => ({
  apiSearch: mockApiSearch,
}));

vi.mock("@/lib/api/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/analytics")>();
  return { ...actual, apiListTeams: mockApiListTeams };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => mockSearchParams,
  usePathname: () => "/app/search",
  useParams: () => ({ id: "call-1" }),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import SearchPage from "@/app/app/search/page";

// ── Helpers ──────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const MOCK_RESULTS = {
  query: "verify identity",
  total: 2,
  results: [
    {
      call_id: "call-1",
      agent_name: "Agent Alpha",
      overall_score: 85,
      band: "quality",
      uploaded_at: new Date().toISOString(),
      snippets: [
        {
          segment_id: "seg-1",
          start_ms: 12000,
          text: "Please verify your identity before we proceed",
          similarity: 0.95,
        },
        {
          segment_id: "seg-2",
          start_ms: 30000,
          text: "I need to verify the account holder identity",
          similarity: 0.82,
        },
      ],
    },
    {
      call_id: "call-2",
      agent_name: "Agent Beta",
      overall_score: 45,
      band: "fail",
      uploaded_at: new Date().toISOString(),
      snippets: [
        {
          segment_id: "seg-3",
          start_ms: 5000,
          text: "The agent did not verify identity at all",
          similarity: 0.78,
        },
      ],
    },
  ],
};

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  mockApiListTeams.mockResolvedValue({ items: [] });
  mockSearchParams.get.mockReturnValue(null);
  mockSearchParams.toString.mockReturnValue("");
});

describe("SearchPage", () => {
  it("renders the initial empty state with example queries", () => {
    withQuery(<SearchPage />);
    expect(screen.getByTestId("search-empty-state")).toBeInTheDocument();
    const examples = screen.getAllByTestId("example-query");
    expect(examples.length).toBeGreaterThanOrEqual(2);
  });

  it("clicking an example query submits a search", async () => {
    const user = userEvent.setup();
    withQuery(<SearchPage />);
    const examples = screen.getAllByTestId("example-query");
    await user.click(examples[0]);
    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("/app/search?q="),
    );
  });

  it("typing a query and pressing Enter submits the search", async () => {
    const user = userEvent.setup();
    withQuery(<SearchPage />);
    const input = screen.getByTestId("search-input");
    await user.clear(input);
    await user.type(input, "billing dispute{enter}");
    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("q=billing+dispute"),
    );
  });

  it("renders grouped result cards with snippets when query matches", async () => {
    mockSearchParams.get.mockReturnValue("verify identity");
    mockApiSearch.mockResolvedValue(MOCK_RESULTS);

    withQuery(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByTestId("search-results")).toBeInTheDocument();
    });

    const cards = screen.getAllByTestId("search-result-card");
    expect(cards).toHaveLength(2);

    const snippetLinks = screen.getAllByTestId("snippet-link");
    expect(snippetLinks.length).toBe(3);
  });

  it("query is reflected in URL search param via push", async () => {
    const user = userEvent.setup();
    withQuery(<SearchPage />);
    const btn = screen.getByTestId("search-submit");
    const input = screen.getByTestId("search-input");
    await user.clear(input);
    await user.type(input, "test query");
    await user.click(btn);
    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("q=test+query"),
    );
  });

  it("snippet link carries ?segment={id}", async () => {
    mockSearchParams.get.mockReturnValue("verify identity");
    mockApiSearch.mockResolvedValue(MOCK_RESULTS);

    withQuery(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByTestId("search-results")).toBeInTheDocument();
    });

    const snippetLinks = screen.getAllByTestId("snippet-link");
    const firstHref = snippetLinks[0].getAttribute("href");
    expect(firstHref).toContain("/app/calls/call-1?segment=seg-1");
  });

  it("highlights matching query terms in snippet text", async () => {
    mockSearchParams.get.mockReturnValue("verify identity");
    mockApiSearch.mockResolvedValue(MOCK_RESULTS);

    withQuery(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByTestId("search-results")).toBeInTheDocument();
    });

    const marks = document.querySelectorAll("mark");
    expect(marks.length).toBeGreaterThan(0);
    const markTexts = Array.from(marks).map((m) => m.textContent?.toLowerCase());
    expect(markTexts.some((t) => t === "verify" || t === "identity")).toBe(true);
  });

  it("renders card-level link to call without segment param", async () => {
    mockSearchParams.get.mockReturnValue("verify identity");
    mockApiSearch.mockResolvedValue(MOCK_RESULTS);

    withQuery(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByTestId("search-results")).toBeInTheDocument();
    });

    const callLinks = screen.getAllByTestId("call-link");
    expect(callLinks[0].getAttribute("href")).toBe("/app/calls/call-1");
  });

  it("renders no-results state", async () => {
    mockSearchParams.get.mockReturnValue("nonexistent mumbo jumbo");
    mockApiSearch.mockResolvedValue({ query: "nonexistent mumbo jumbo", results: [], total: 0 });

    withQuery(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByTestId("search-no-results")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/no calls matched/i),
    ).toBeInTheDocument();
  });

  it("shows score badge with band color", async () => {
    mockSearchParams.get.mockReturnValue("verify identity");
    mockApiSearch.mockResolvedValue(MOCK_RESULTS);

    withQuery(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByTestId("search-results")).toBeInTheDocument();
    });

    const badges = screen.getAllByTestId("score-badge");
    expect(badges.length).toBe(2);
    expect(badges[0].textContent).toContain("85");
    expect(badges[1].textContent).toContain("45");
  });

  it("shows similarity indicator on snippets", async () => {
    mockSearchParams.get.mockReturnValue("verify identity");
    mockApiSearch.mockResolvedValue(MOCK_RESULTS);

    withQuery(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByTestId("search-results")).toBeInTheDocument();
    });

    const simBadges = screen.getAllByTestId("similarity-badge");
    expect(simBadges.length).toBe(3);
    expect(simBadges[0].textContent).toBe("95%");
  });
});
