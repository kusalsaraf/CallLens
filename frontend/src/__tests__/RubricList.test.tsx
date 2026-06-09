import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mocks ──────────────────────────────────────────────────────────────

const {
  mockListRubrics,
  mockActivateRubric,
  mockCloneRubric,
  mockDeleteRubric,
  mockPush,
} = vi.hoisted(() => ({
  mockListRubrics: vi.fn(),
  mockActivateRubric: vi.fn(),
  mockCloneRubric: vi.fn(),
  mockDeleteRubric: vi.fn(),
  mockPush: vi.fn(),
}));

vi.mock("@/lib/api/rubrics", () => ({
  apiListRubrics: mockListRubrics,
  apiActivateRubric: mockActivateRubric,
  apiCloneRubric: mockCloneRubric,
  apiDeleteRubric: mockDeleteRubric,
  DIMENSION_KINDS: [
    "sentiment_empathy",
    "script_adherence",
    "compliance",
    "objection_handling",
    "talk_listen",
    "outcome",
    "custom",
  ],
  KIND_LABELS: {
    sentiment_empathy: "Sentiment & Empathy",
    script_adherence: "Script Adherence",
    compliance: "Compliance",
    objection_handling: "Objection Handling",
    talk_listen: "Talk/Listen Ratio",
    outcome: "Call Outcome",
    custom: "Custom",
  },
  KIND_HINTS: {
    sentiment_empathy: "Scores the agent's tone.",
    script_adherence: "Checks call structure.",
    compliance: "Checks required phrases.",
    objection_handling: "Scores objection handling.",
    talk_listen: "Deterministic ratio score.",
    outcome: "Call outcome.",
    custom: "Custom criteria.",
  },
}));

vi.mock("@/lib/api/client", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    body: Record<string, unknown>;
    constructor(status: number, body: Record<string, unknown>) {
      super("api error");
      this.status = status;
      this.body = body;
    }
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({ get: () => null, toString: () => "" }),
  usePathname: () => "/app/rubrics",
  useParams: () => ({ id: "r1" }),
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

import RubricsPage from "@/app/app/rubrics/page";

// ── Helpers ──────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const MOCK_RUBRICS = {
  items: [
    {
      id: "r1",
      name: "Support QA",
      description: "Default rubric",
      is_active: true,
      is_default: true,
      created_at: new Date().toISOString(),
    },
    {
      id: "r2",
      name: "Sales QA",
      description: null,
      is_active: false,
      is_default: false,
      created_at: new Date().toISOString(),
    },
  ],
};

// ── Tests ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RubricsPage", () => {
  it("renders rubric list with ACTIVE badge on the active one", async () => {
    mockListRubrics.mockResolvedValue(MOCK_RUBRICS);
    withQuery(<RubricsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("rubrics-list")).toBeInTheDocument();
    });

    const rows = screen.getAllByTestId("rubric-row");
    expect(rows).toHaveLength(2);

    const badges = screen.getAllByTestId("active-badge");
    expect(badges).toHaveLength(1);
    expect(badges[0].textContent).toBe("Active");
  });

  it("does not show Activate or Delete buttons on the active rubric", async () => {
    mockListRubrics.mockResolvedValue(MOCK_RUBRICS);
    withQuery(<RubricsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("rubrics-list")).toBeInTheDocument();
    });

    // The active rubric (Support QA) should not have Activate or Delete buttons
    const activateButtons = screen.getAllByTestId("activate-btn");
    expect(activateButtons).toHaveLength(1); // Only the inactive one

    const deleteButtons = screen.getAllByTestId("delete-btn");
    expect(deleteButtons).toHaveLength(1);
  });

  it("clone calls apiCloneRubric", async () => {
    mockListRubrics.mockResolvedValue(MOCK_RUBRICS);
    mockCloneRubric.mockResolvedValue({ ...MOCK_RUBRICS.items[0], id: "r3", name: "Support QA (copy)" });
    const user = userEvent.setup();

    withQuery(<RubricsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("rubrics-list")).toBeInTheDocument();
    });

    const cloneButtons = screen.getAllByTestId("clone-btn");
    await user.click(cloneButtons[0]);

    expect(mockCloneRubric).toHaveBeenCalled();
    expect(mockCloneRubric.mock.calls[0][0]).toBe("r1");
  });

  it("activate shows confirm dialog and calls apiActivateRubric", async () => {
    mockListRubrics.mockResolvedValue(MOCK_RUBRICS);
    mockActivateRubric.mockResolvedValue({ ...MOCK_RUBRICS.items[1], is_active: true });
    const user = userEvent.setup();

    withQuery(<RubricsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("rubrics-list")).toBeInTheDocument();
    });

    const activateBtn = screen.getByTestId("activate-btn");
    await user.click(activateBtn);

    // Confirm dialog should appear
    expect(screen.getByText(/Make this the active rubric/)).toBeInTheDocument();

    const confirmBtn = screen.getByTestId("confirm-action");
    await user.click(confirmBtn);

    expect(mockActivateRubric).toHaveBeenCalled();
    expect(mockActivateRubric.mock.calls[0][0]).toBe("r2");
  });

  it("delete 409 shows the server's reason inline", async () => {
    mockListRubrics.mockResolvedValue(MOCK_RUBRICS);
    const { ApiError } = await import("@/lib/api/client");
    mockDeleteRubric.mockRejectedValue(
      new ApiError(409, { detail: "Cannot delete a rubric referenced by existing calls" }),
    );
    const user = userEvent.setup();

    withQuery(<RubricsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("rubrics-list")).toBeInTheDocument();
    });

    const deleteBtn = screen.getByTestId("delete-btn");
    await user.click(deleteBtn);

    const confirmBtn = screen.getByTestId("confirm-action");
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(screen.getByTestId("delete-error")).toBeInTheDocument();
    });

    expect(screen.getByText(/Cannot delete a rubric referenced/)).toBeInTheDocument();
  });

  it("renders loading state", async () => {
    mockListRubrics.mockReturnValue(new Promise(() => {})); // never resolves
    withQuery(<RubricsPage />);

    expect(screen.getByTestId("rubrics-loading")).toBeInTheDocument();
  });
});
