import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/auth/LoginForm";

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockLogin = vi.fn();
const mockReplace = vi.fn();

vi.mock("@/providers/AuthProvider", () => ({
  useAuth: () => ({ login: mockLogin }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

// next/link renders a plain <a> in the test environment
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
  }: {
    href: string;
    children: React.ReactNode;
  }) => <a href={href}>{children}</a>,
}));

// ── Tests ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockLogin.mockReset();
  mockReplace.mockReset();
});

afterEach(() => vi.clearAllMocks());

describe("LoginForm validation", () => {
  it("shows field errors when submitted empty", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/enter a valid email/i)
      ).toBeInTheDocument();
    });
  });

  it("shows error for invalid email", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "not-an-email");
    await user.type(screen.getByLabelText(/password/i), "secret123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText(/enter a valid email/i)).toBeInTheDocument()
    );
  });
});

describe("LoginForm submission", () => {
  it("calls login with email and password on valid submit", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "owner@example.com");
    await user.type(screen.getByLabelText(/password/i), "secret123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith("owner@example.com", "secret123")
    );
    expect(mockReplace).toHaveBeenCalledWith("/app");
  });

  it("shows generic server error on API failure", async () => {
    const { ApiError } = await import("@/lib/api/client");
    mockLogin.mockRejectedValueOnce(new ApiError(500, { message: "oops" }));
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "owner@example.com");
    await user.type(screen.getByLabelText(/password/i), "secret123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    );
  });

  it("shows credential error on 401", async () => {
    const { ApiError } = await import("@/lib/api/client");
    mockLogin.mockRejectedValueOnce(
      new ApiError(401, { error: "authentication_required" })
    );
    const user = userEvent.setup();
    render(<LoginForm />);

    await user.type(screen.getByLabelText(/email/i), "owner@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrongpass");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/incorrect email or password/i)
      ).toBeInTheDocument()
    );
  });
});
