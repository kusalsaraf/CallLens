import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { SegmentOut } from "@/lib/api/calls";
import { TranscriptPanel } from "@/components/calls/TranscriptPanel";

// ── Helpers ──────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ── Redacted segment fixtures ────────────────────────────────────────────────

const RAW_EMAIL = "Please email me at john@example.com for details";
const REDACTED_EMAIL =
  "Please email me at [REDACTED_EMAIL] for details";

const SEGMENTS_WITH_REDACTION: SegmentOut[] = [
  {
    id: "s1",
    sequence: 0,
    start_ms: 0,
    end_ms: 4000,
    text: RAW_EMAIL,
    redacted_text: REDACTED_EMAIL,
    speaker: "agent",
  },
  {
    id: "s2",
    sequence: 1,
    start_ms: 4500,
    end_ms: 9000,
    text: "My card number is 4111-1111-1111-1111",
    redacted_text: "My card number is [REDACTED_CARD]",
    speaker: "customer",
  },
  {
    id: "s3",
    sequence: 2,
    start_ms: 9500,
    end_ms: 14000,
    text: "No PII here, just a plain question",
    redacted_text: null,
    speaker: "agent",
  },
];

const ENTITIES: Record<string, number> = {
  EMAIL: 1,
  CARD: 1,
};

// ── TranscriptPanel redaction tests ──────────────────────────────────────────

describe("TranscriptPanel — redaction", () => {
  it("defaults to REDACTED view (shows redacted_text, hides raw PII)", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={vi.fn()}
        entitiesRedacted={ENTITIES}
        redactionProvider="regex"
      />,
    );

    const textEls = screen.getAllByTestId("segment-text");
    expect(textEls[0].textContent).toContain("[REDACTED_EMAIL]");
    expect(textEls[0].textContent).not.toContain("john@example.com");

    expect(textEls[1].textContent).toContain("[REDACTED_CARD]");
    expect(textEls[1].textContent).not.toContain("4111-1111-1111-1111");

    expect(textEls[2].textContent).toBe("No PII here, just a plain question");
  });

  it("toggling to 'Show original' reveals raw text", async () => {
    const user = userEvent.setup();
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={vi.fn()}
        entitiesRedacted={ENTITIES}
        redactionProvider="regex"
      />,
    );

    const toggle = screen.getByTestId("redaction-toggle");
    expect(toggle.textContent).toBe("Show original");

    await user.click(toggle);

    const textEls = screen.getAllByTestId("segment-text");
    expect(textEls[0].textContent).toContain("john@example.com");
    expect(textEls[1].textContent).toContain("4111-1111-1111-1111");

    expect(screen.getByTestId("original-notice")).toBeInTheDocument();
  });

  it("toggling back re-redacts", async () => {
    const user = userEvent.setup();
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={vi.fn()}
        entitiesRedacted={ENTITIES}
        redactionProvider="regex"
      />,
    );

    const toggle = screen.getByTestId("redaction-toggle");
    await user.click(toggle); // show original
    await user.click(toggle); // back to redacted

    const textEls = screen.getAllByTestId("segment-text");
    expect(textEls[0].textContent).toContain("[REDACTED_EMAIL]");
    expect(textEls[0].textContent).not.toContain("john@example.com");
    expect(screen.queryByTestId("original-notice")).toBeNull();
  });

  it("no toggle shown when segments have no redacted_text", () => {
    const plainSegments: SegmentOut[] = [
      {
        id: "p1",
        sequence: 0,
        start_ms: 0,
        end_ms: 3000,
        text: "Hello there",
        redacted_text: null,
        speaker: "agent",
      },
    ];
    render(
      <TranscriptPanel
        segments={plainSegments}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("redaction-toggle")).toBeNull();
  });
});

// ── PII indicator tests ──────────────────────────────────────────────────────

describe("TranscriptPanel — PII indicator", () => {
  it("renders typed entity counts", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={vi.fn()}
        entitiesRedacted={ENTITIES}
        redactionProvider="regex"
      />,
    );

    const indicator = screen.getByTestId("pii-indicator");
    expect(indicator.textContent).toContain("1 email");
    expect(indicator.textContent).toContain("1 card");
  });

  it("shows 'No PII detected' when redaction ran but found nothing", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={vi.fn()}
        entitiesRedacted={{}}
        redactionProvider="regex"
      />,
    );

    expect(screen.queryByTestId("pii-indicator")).toBeNull();
    expect(screen.getByTestId("no-pii")).toBeInTheDocument();
    expect(screen.getByTestId("no-pii").textContent).toContain("No PII detected");
  });

  it("shows nothing when no redaction provider", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );

    expect(screen.queryByTestId("pii-indicator")).toBeNull();
    expect(screen.queryByTestId("no-pii")).toBeNull();
  });
});

// ── Evidence / focus tests in both views ─────────────────────────────────────

describe("TranscriptPanel — focus in both views", () => {
  it("focused segment is marked in redacted (default) view", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={vi.fn()}
        focusedSegmentId="s2"
        entitiesRedacted={ENTITIES}
        redactionProvider="regex"
      />,
    );

    const focusedEl = document.querySelector("[data-focused]");
    expect(focusedEl).not.toBeNull();
    expect(focusedEl!.textContent).toContain("[REDACTED_CARD]");
  });

  it("focused segment is marked in original view", async () => {
    const user = userEvent.setup();
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={vi.fn()}
        focusedSegmentId="s2"
        entitiesRedacted={ENTITIES}
        redactionProvider="regex"
      />,
    );

    await user.click(screen.getByTestId("redaction-toggle"));

    const focusedEl = document.querySelector("[data-focused]");
    expect(focusedEl).not.toBeNull();
    expect(focusedEl!.textContent).toContain("4111-1111-1111-1111");
  });

  it("clicking a segment calls onSeek in both views", async () => {
    const onSeek = vi.fn();
    const user = userEvent.setup();
    render(
      <TranscriptPanel
        segments={SEGMENTS_WITH_REDACTION}
        currentTimeSec={0}
        onSeek={onSeek}
        entitiesRedacted={ENTITIES}
        redactionProvider="regex"
      />,
    );

    const textEls = screen.getAllByTestId("segment-text");
    await user.click(textEls[1]);
    expect(onSeek).toHaveBeenCalledWith(4500);

    await user.click(screen.getByTestId("redaction-toggle"));
    await user.click(textEls[1]);
    expect(onSeek).toHaveBeenCalledWith(4500);
    expect(onSeek).toHaveBeenCalledTimes(2);
  });
});

// ── Search snippet redaction test ────────────────────────────────────────────

const { mockApiSearch, mockApiListTeams, mockPush, mockSearchParams } =
  vi.hoisted(() => ({
    mockApiSearch: vi.fn(),
    mockApiListTeams: vi.fn(),
    mockPush: vi.fn(),
    mockSearchParams: {
      get: vi.fn().mockReturnValue(null),
      toString: vi.fn().mockReturnValue(""),
    },
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

describe("Search snippets — redacted", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiListTeams.mockResolvedValue({ items: [] });
  });

  it("renders redacted snippet text with highlighting and no raw PII", async () => {
    mockSearchParams.get.mockReturnValue("email");
    mockApiSearch.mockResolvedValue({
      query: "email",
      total: 1,
      results: [
        {
          call_id: "c1",
          agent_name: "Agent X",
          overall_score: 80,
          band: "quality",
          uploaded_at: new Date().toISOString(),
          snippets: [
            {
              segment_id: "seg-r1",
              start_ms: 1000,
              text: "Please email me at [REDACTED_EMAIL] for help",
              similarity: 0.88,
            },
          ],
        },
      ],
    });

    withQuery(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByTestId("search-results")).toBeInTheDocument();
    });

    const snippetLinks = screen.getAllByTestId("snippet-link");
    expect(snippetLinks[0].textContent).toContain("[REDACTED_EMAIL]");
    expect(snippetLinks[0].textContent).not.toContain("john@example.com");

    const marks = document.querySelectorAll("mark");
    const markTexts = Array.from(marks).map((m) => m.textContent?.toLowerCase());
    expect(markTexts).toContain("email");
  });
});
