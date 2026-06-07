import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/providers/AuthProvider";

// Capture fetch calls
const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.restoreAllMocks();
  fetchMock.mockReset();
});

function TestConsumer() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <p>loading</p>;
  return <p data-testid="user">{user ? user.email : "none"}</p>;
}

const mockUser = {
  id: "abc-123",
  email: "owner@example.com",
  name: "Owner",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

describe("AuthProvider bootstrap", () => {
  it("sets user after successful silent refresh + /me", async () => {
    fetchMock
      // POST /api/v1/auth/refresh
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: "tok",
          token_type: "bearer",
          expires_in: 900,
        }),
      })
      // GET /api/v1/auth/me
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    expect(screen.getByText("loading")).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByTestId("user").textContent).toBe("owner@example.com")
    );
  });

  it("leaves user as null when refresh fails", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, json: async () => ({}) });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId("user").textContent).toBe("none")
    );
  });
});
