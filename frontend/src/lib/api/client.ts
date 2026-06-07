"use client";

/** Access token kept in module scope — never persisted to localStorage. */
let _token: string | null = null;

export const tokenStore = {
  get: (): string | null => _token,
  set: (t: string | null): void => {
    _token = t;
  },
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: Record<string, unknown>
  ) {
    super((body.message as string | undefined) ?? `HTTP ${status}`);
    this.name = "ApiError";
  }
}

async function silentRefresh(): Promise<boolean> {
  try {
    const resp = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (!resp.ok) return false;
    const data = (await resp.json()) as { access_token: string };
    tokenStore.set(data.access_token);
    return true;
  } catch {
    return false;
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };

  const token = tokenStore.get();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(path, { ...init, headers, credentials: "include" });

  if (resp.status === 401 && token) {
    const refreshed = await silentRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${tokenStore.get()}`;
      const retry = await fetch(path, {
        ...init,
        headers,
        credentials: "include",
      });
      if (!retry.ok) {
        const errBody = (await retry.json().catch(() => ({}))) as Record<
          string,
          unknown
        >;
        throw new ApiError(retry.status, errBody);
      }
      if (retry.status === 204) return undefined as T;
      return retry.json() as Promise<T>;
    }
    // Refresh failed — clear token and redirect
    tokenStore.set(null);
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new ApiError(401, {
      error: "session_expired",
      message: "Session expired",
    });
  }

  if (!resp.ok) {
    const errBody = (await resp.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    throw new ApiError(resp.status, errBody);
  }

  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}
