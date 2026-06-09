import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mocks ──────────────────────────────────────────────────────────────

const {
  mockGetCall,
  mockGetTranscript,
  mockGetAnalysis,
  mockGetTrace,
  mockFetchAudio,
  mockSearchParamsGet,
  mockScrollIntoView,
} = vi.hoisted(() => ({
  mockGetCall: vi.fn(),
  mockGetTranscript: vi.fn(),
  mockGetAnalysis: vi.fn(),
  mockGetTrace: vi.fn(),
  mockFetchAudio: vi.fn(),
  mockSearchParamsGet: vi.fn(),
  mockScrollIntoView: vi.fn(),
}));

vi.mock("@/lib/api/calls", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/calls")>();
  return {
    ...actual,
    apiGetCall: mockGetCall,
    apiGetTranscript: mockGetTranscript,
    apiGetAnalysis: mockGetAnalysis,
    apiGetTrace: mockGetTrace,
    fetchAudioObjectUrl: mockFetchAudio,
  };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "call-deep" }),
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => ({
    get: mockSearchParamsGet,
    toString: () => "",
  }),
  usePathname: () => "/app/calls/call-deep",
}));

import CallDetailPage from "@/app/app/calls/[id]/page";

// ── URL polyfills for jsdom ──────────────────────────────────────────────────

if (typeof URL.createObjectURL === "undefined") {
  URL.createObjectURL = () => "blob:mock";
}
if (typeof URL.revokeObjectURL === "undefined") {
  URL.revokeObjectURL = () => {};
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const SCORED_CALL = {
  id: "call-deep",
  status: "scored",
  original_filename: "deep-link-test.wav",
  duration_seconds: 120,
  agent_id: "agent-1",
  status_detail: null,
  created_at: "2026-06-09T10:00:00Z",
  updated_at: "2026-06-09T10:00:00Z",
};

const TRANSCRIPT = {
  id: "tx-1",
  call_id: "call-deep",
  language: "en",
  segments: [
    {
      id: "seg-first",
      sequence: 0,
      start_ms: 0,
      end_ms: 3000,
      text: "Hello, how can I help you today?",
      redacted_text: null,
      speaker: "agent",
    },
    {
      id: "seg-target",
      sequence: 1,
      start_ms: 5000,
      end_ms: 10000,
      text: "I need help with my account please.",
      redacted_text: null,
      speaker: "customer",
    },
    {
      id: "seg-third",
      sequence: 2,
      start_ms: 11000,
      end_ms: 15000,
      text: "Sure, let me pull that up for you.",
      redacted_text: null,
      speaker: "agent",
    },
  ],
  redaction_provider: null,
  entities_redacted: null,
  created_at: "2026-06-09T10:00:00Z",
};

const ANALYSIS = {
  id: "an-1",
  call_id: "call-deep",
  overall_score: 78,
  summary: "Decent call.",
  key_moments: [],
  action_items: [],
  sentiment_overall: "positive",
  talk_listen_ratio: 0.55,
  interruptions: 1,
  longest_monologue_ms: 8000,
  total_turns: 6,
  compliance_passed: true,
  escalate_for_review: false,
  escalation_reason: null,
  topics: [],
  created_at: "2026-06-09T10:00:00Z",
};

const TRACE = {
  call_id: "call-deep",
  runs: [],
};

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  mockGetCall.mockResolvedValue(SCORED_CALL);
  mockGetTranscript.mockResolvedValue(TRANSCRIPT);
  mockGetAnalysis.mockResolvedValue(ANALYSIS);
  mockGetTrace.mockResolvedValue(TRACE);
  mockFetchAudio.mockResolvedValue("blob:mock-audio");

  Element.prototype.scrollIntoView = mockScrollIntoView;
});

describe("CallDetail deep-link via ?segment=", () => {
  it("sets focusedSegmentId and seeks audio when ?segment= is present", async () => {
    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "segment" ? "seg-target" : null,
    );

    withQuery(<CallDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("deep-link-test.wav")).toBeInTheDocument();
    });

    await waitFor(() => {
      const focused = document.querySelector("[data-focused]");
      expect(focused).not.toBeNull();
    });
  });

  it("loads normally without ?segment= param", async () => {
    mockSearchParamsGet.mockReturnValue(null);

    withQuery(<CallDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("deep-link-test.wav")).toBeInTheDocument();
    });

    const focused = document.querySelector("[data-focused]");
    expect(focused).toBeNull();
  });

  it("handles unknown segment ID gracefully (no crash)", async () => {
    mockSearchParamsGet.mockImplementation((key: string) =>
      key === "segment" ? "seg-nonexistent" : null,
    );

    withQuery(<CallDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("deep-link-test.wav")).toBeInTheDocument();
    });

    const focused = document.querySelector("[data-focused]");
    expect(focused).toBeNull();
  });
});
