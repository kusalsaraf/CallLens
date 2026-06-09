import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Hoist mocks ──────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: () => null, toString: () => "" }),
  usePathname: () => "/app/rubrics/new",
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

import {
  RubricBuilder,
  formToApiPayload,
  type RubricFormData,
} from "@/components/rubrics/RubricBuilder";
import type { RubricDetailOut } from "@/lib/api/rubrics";

// ── Helpers ──────────────────────────────────────────────────────────────────

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ── Tests ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RubricBuilder", () => {
  it("renders empty form in create mode", () => {
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    expect(screen.getByLabelText("Rubric Name")).toBeInTheDocument();
    expect(screen.getByTestId("rubric-form")).toBeInTheDocument();
    expect(screen.getAllByTestId("dimension-row")).toHaveLength(1);
  });

  it("renders prefilled form in edit mode", () => {
    const rubric: RubricDetailOut = {
      id: "r1",
      name: "My Rubric",
      description: "A test rubric",
      is_active: false,
      is_default: false,
      created_at: new Date().toISOString(),
      dimensions: [
        {
          id: "d1",
          key: "sent",
          name: "Sentiment",
          weight: 0.5,
          kind: "sentiment_empathy",
          config: null,
          created_at: new Date().toISOString(),
        },
        {
          id: "d2",
          key: "comp",
          name: "Compliance",
          weight: 0.5,
          kind: "compliance",
          config: { required_phrases: ["Hello", "Goodbye"] },
          created_at: new Date().toISOString(),
        },
      ],
    };
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder rubric={rubric} onSubmit={onSubmit} />);

    expect(screen.getByDisplayValue("My Rubric")).toBeInTheDocument();
    expect(screen.getAllByTestId("dimension-row")).toHaveLength(2);
  });

  it("switching kind to compliance reveals phrase input", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    const kindSelect = screen.getByTestId("dim-kind");
    await user.selectOptions(kindSelect, "compliance");

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Add a required phrase…")).toBeInTheDocument();
    });
  });

  it("switching kind to script_adherence reveals checklist", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    const kindSelect = screen.getByTestId("dim-kind");
    await user.selectOptions(kindSelect, "script_adherence");

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Add a checklist step…")).toBeInTheDocument();
    });
  });

  it("switching kind to custom reveals guidance textarea", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    const kindSelect = screen.getByTestId("dim-kind");
    await user.selectOptions(kindSelect, "custom");

    await waitFor(() => {
      expect(screen.getByTestId("dim-guidance")).toBeInTheDocument();
    });
  });

  it("switching kind swaps the config inputs", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    const kindSelect = screen.getByTestId("dim-kind");

    // Switch to compliance
    await user.selectOptions(kindSelect, "compliance");
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Add a required phrase…")).toBeInTheDocument();
    });

    // Switch to custom — phrase input should disappear
    await user.selectOptions(kindSelect, "custom");
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Add a required phrase…")).not.toBeInTheDocument();
      expect(screen.getByTestId("dim-guidance")).toBeInTheDocument();
    });
  });

  it("add and remove dimensions", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    expect(screen.getAllByTestId("dimension-row")).toHaveLength(1);

    const addBtn = screen.getByTestId("add-dimension");
    await user.click(addBtn);

    expect(screen.getAllByTestId("dimension-row")).toHaveLength(2);

    const removeBtn = screen.getAllByTestId("remove-dimension")[0];
    await user.click(removeBtn);

    expect(screen.getAllByTestId("dimension-row")).toHaveLength(1);
  });

  it("normalized weight % updates live", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    // Add a second dimension
    await user.click(screen.getByTestId("add-dimension"));

    // Both dims default to weight=1, so each should show 50.0%
    const pcts = screen.getAllByTestId("weight-pct");
    await waitFor(() => {
      expect(pcts).toHaveLength(2);
      expect(pcts[0].textContent).toBe("50.0%");
      expect(pcts[1].textContent).toBe("50.0%");
    });
  });

  it("validation blocks submit when name is empty", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    // Don't fill in name, just try to submit
    const submitBtn = screen.getByTestId("rubric-submit");
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getAllByText("Name is required").length).toBeGreaterThanOrEqual(1);
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("validation blocks submit when compliance has no phrases", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    // Fill name
    await user.type(screen.getByLabelText("Rubric Name"), "Test");

    // Fill dimension name and key
    await user.type(screen.getByTestId("dim-name"), "Compliance");
    const keyInput = screen.getByPlaceholderText("e.g. empathy");
    await user.type(keyInput, "comp");

    // Switch to compliance — no phrases added
    const kindSelect = screen.getByTestId("dim-kind");
    await user.selectOptions(kindSelect, "compliance");

    // Try to submit
    await user.click(screen.getByTestId("rubric-submit"));

    await waitFor(() => {
      expect(screen.getByText("At least one required phrase is needed")).toBeInTheDocument();
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("validation blocks submit when custom has empty guidance", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Rubric Name"), "Test");
    await user.type(screen.getByTestId("dim-name"), "Custom");
    const keyInput = screen.getByPlaceholderText("e.g. empathy");
    await user.type(keyInput, "cust");

    const kindSelect = screen.getByTestId("dim-kind");
    await user.selectOptions(kindSelect, "custom");

    await user.click(screen.getByTestId("rubric-submit"));

    await waitFor(() => {
      expect(screen.getByText("Guidance is required for custom dimensions")).toBeInTheDocument();
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("valid form submits with correct payload", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    withQuery(<RubricBuilder onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Rubric Name"), "Test Rubric");

    // Fill dimension
    await user.type(screen.getByTestId("dim-name"), "Sentiment");
    const keyInput = screen.getByPlaceholderText("e.g. empathy");
    await user.type(keyInput, "sent");

    await user.click(screen.getByTestId("rubric-submit"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    const data = onSubmit.mock.calls[0][0] as RubricFormData;
    expect(data.name).toBe("Test Rubric");
    expect(data.dimensions).toHaveLength(1);
    expect(data.dimensions[0].kind).toBe("sentiment_empathy");
  });

  it("formToApiPayload builds compliance config correctly", () => {
    const data: RubricFormData = {
      name: "Test",
      description: "",
      dimensions: [
        {
          key: "comp",
          name: "Compliance",
          weight: 1,
          kind: "compliance",
          config_phrases: ["Hello", "Goodbye"],
          config_checklist: [],
          config_guidance: "",
        },
      ],
    };
    const payload = formToApiPayload(data);
    expect(payload.dimensions[0].config).toEqual({
      required_phrases: ["Hello", "Goodbye"],
    });
  });

  it("formToApiPayload builds custom config correctly", () => {
    const data: RubricFormData = {
      name: "Test",
      dimensions: [
        {
          key: "cust",
          name: "Custom",
          weight: 1,
          kind: "custom",
          config_phrases: [],
          config_checklist: [],
          config_guidance: "Score patience",
        },
      ],
    };
    const payload = formToApiPayload(data);
    expect(payload.dimensions[0].config).toEqual({ guidance: "Score patience" });
  });

  it("shows server error when provided", () => {
    const onSubmit = vi.fn();
    withQuery(
      <RubricBuilder onSubmit={onSubmit} serverError="Something went wrong" />,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
