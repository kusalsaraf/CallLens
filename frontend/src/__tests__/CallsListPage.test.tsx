import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CallListOut } from "@/lib/api/calls";

// ── Mocks ──────────────────────────────────────────────────────────────────────
const { mockListCalls } = vi.hoisted(() => ({ mockListCalls: vi.fn() }));
vi.mock("@/lib/api/calls", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/calls")>();
  return { ...actual, apiListCalls: mockListCalls };
});
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/app/calls",
}));
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
  }: {
    href: string;
    children: React.ReactNode;
  }) => <a href={href}>{children}</a>,
}));

import CallsPage from "@/app/app/calls/page";

// ── Helpers ───────────────────────────────────────────────────────────────────
function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const EMPTY_LIST: CallListOut = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
};

const LIST_WITH_CALLS: CallListOut = {
  items: [
    {
      id: "call-1",
      status: "transcribed",
      original_filename: "sales-call.wav",
      duration_seconds: 125,
      agent_id: "agent-1",
      status_detail: null,
      created_at: new Date(Date.now() - 3600_000).toISOString(),
      updated_at: new Date(Date.now() - 3600_000).toISOString(),
    },
    {
      id: "call-2",
      status: "failed",
      original_filename: "support-call.mp3",
      duration_seconds: null,
      agent_id: null,
      status_detail: "transcriber error",
      created_at: new Date(Date.now() - 7200_000).toISOString(),
      updated_at: new Date(Date.now() - 7200_000).toISOString(),
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => mockListCalls.mockReset());
afterEach(() => vi.clearAllMocks());

describe("CallsPage", () => {
  it("shows empty state when there are no calls", async () => {
    mockListCalls.mockResolvedValueOnce(EMPTY_LIST);
    render(<CallsPage />, { wrapper });
    await waitFor(() =>
      expect(screen.getByText(/no calls yet/i)).toBeInTheDocument(),
    );
  });

  it("renders a row for each call with status badge", async () => {
    mockListCalls.mockResolvedValueOnce(LIST_WITH_CALLS);
    render(<CallsPage />, { wrapper });
    await waitFor(() =>
      expect(screen.getByText("sales-call.wav")).toBeInTheDocument(),
    );
    expect(screen.getByText("support-call.mp3")).toBeInTheDocument();
    // Status labels appear in both the filter select and the badge — check at least one
    expect(screen.getAllByText("Transcribed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Failed").length).toBeGreaterThan(0);
  });

  it("renders duration in MM:SS format", async () => {
    mockListCalls.mockResolvedValueOnce(LIST_WITH_CALLS);
    render(<CallsPage />, { wrapper });
    await waitFor(() =>
      // 125s = 02:05
      expect(screen.getByText("02:05")).toBeInTheDocument(),
    );
  });

  it("each row links to /app/calls/{id}", async () => {
    mockListCalls.mockResolvedValueOnce(LIST_WITH_CALLS);
    render(<CallsPage />, { wrapper });
    await waitFor(() =>
      expect(screen.getByText("sales-call.wav")).toBeInTheDocument(),
    );
    const link = screen.getByRole("link", { name: /sales-call\.wav/i });
    expect(link).toHaveAttribute("href", "/app/calls/call-1");
  });
});
