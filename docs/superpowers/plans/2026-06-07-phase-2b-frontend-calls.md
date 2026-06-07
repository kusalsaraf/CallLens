# Phase 2B Frontend: Call Upload, List, and Detail

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the upload flow (drag-and-drop with live SSE progress), calls list table, and call-detail page (audio player two-way synced to transcript) for CallLens Phase 2B.

**Architecture:** All new pages live under the existing `/app` authenticated shell. TanStack Query manages server state. SSE is implemented via `fetch + ReadableStream` (not `EventSource`) so the Bearer token can be sent. Audio is fetched as a blob and fed to `<audio>` via an object URL so the Bearer token can be sent. Upload uses `XMLHttpRequest` for progress events. No new npm packages are required.

**Tech Stack:** Next.js 15, React 19, TanStack Query v5, Tailwind CSS (existing design tokens), Radix UI, Vitest + RTL.

---

## File Map

### New files
| File | Purpose |
|------|---------|
| `frontend/src/lib/api/calls.ts` | All calls API types + functions |
| `frontend/src/components/calls/StatusBadge.tsx` | Status badge with semantic colours |
| `frontend/src/components/calls/CallStatusStepper.tsx` | SSE-driven live status stepper |
| `frontend/src/components/calls/UploadDropzone.tsx` | Drag-and-drop file picker with validation |
| `frontend/src/components/calls/AudioPlayer.tsx` | Audio player with seek and playback-rate |
| `frontend/src/components/calls/TranscriptPanel.tsx` | Transcript with two-way audio sync |
| `frontend/src/app/app/upload/page.tsx` | Upload page (centered card, dropzone) |
| `frontend/src/app/app/calls/page.tsx` | Calls list (table, filters, pagination) |
| `frontend/src/app/app/calls/[id]/page.tsx` | Call detail (header + player + transcript) |
| `frontend/src/__tests__/CallStatusStepper.test.tsx` | SSE stepper unit tests |
| `frontend/src/__tests__/UploadDropzone.test.tsx` | Dropzone validation + submit tests |
| `frontend/src/__tests__/CallsListPage.test.tsx` | List page row + badge + link tests |
| `frontend/src/__tests__/TranscriptPanel.test.tsx` | Seek + highlight unit tests |

### Modified files
| File | Change |
|------|--------|
| `frontend/src/lib/api/client.ts` | Handle 204 No Content in `apiFetch` |
| `frontend/src/lib/utils.ts` | Add `formatDuration`, `formatRelative` |
| `frontend/src/app/app/page.tsx` | Server-side redirect to `/app/calls` |
| `frontend/src/components/app/Sidebar.tsx` | Remove `placeholder` from Calls; add Upload link |
| `frontend/src/components/app/TopBar.tsx` | Add "Upload recording" button |

---

## Task 1 — Patch `apiFetch`, extend `utils.ts`, and create the calls API layer

**Files:**
- Modify: `frontend/src/lib/api/client.ts`
- Modify: `frontend/src/lib/utils.ts`
- Create: `frontend/src/lib/api/calls.ts`

- [ ] **Step 1: Patch `apiFetch` to handle 204 No Content**

The DELETE endpoint returns 204 with no body; `resp.json()` would throw. Open
`frontend/src/lib/api/client.ts` and replace the two `return resp.json()` / retry
`return retry.json()` lines so the full bottom section reads:

```ts
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
```

- [ ] **Step 2: Add `formatDuration` and `formatRelative` to `utils.ts`**

Open `frontend/src/lib/utils.ts` and append:

```ts
/** Format seconds as MM:SS, or "--:--" if null. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds)) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** Format an ISO timestamp as a human-readable relative string. */
export function formatRelative(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
```

- [ ] **Step 3: Create `frontend/src/lib/api/calls.ts`**

```ts
"use client";

import { ApiError, apiFetch, tokenStore } from "./client";
import { apiRefresh } from "./auth";

// ─── Types ────────────────────────────────────────────────────────────────────

export type CallStatus =
  | "uploaded"
  | "transcribing"
  | "diarizing"
  | "transcribed"
  | "failed";

export const TERMINAL_STATUSES = new Set<CallStatus>([
  "transcribed",
  "failed",
]);

export function isTerminalStatus(status: CallStatus): boolean {
  return TERMINAL_STATUSES.has(status);
}

export interface CallOut {
  id: string;
  status: CallStatus;
  original_filename: string;
  duration_seconds: number | null;
  agent_id: string | null;
  status_detail: string | null;
  created_at: string;
  updated_at: string;
}

export interface CallListOut {
  items: CallOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface SegmentOut {
  id: string;
  sequence: number;
  start_ms: number;
  end_ms: number;
  text: string;
  speaker: "agent" | "customer" | "unknown";
}

export interface TranscriptOut {
  id: string;
  call_id: string;
  language: string | null;
  segments: SegmentOut[];
  created_at: string;
}

export interface SsePayload {
  status: string;
  detail?: string;
}

export interface ListCallsParams {
  status?: string;
  page?: number;
  page_size?: number;
}

// ─── Client-side validation constants (mirror backend) ───────────────────────

export const ALLOWED_AUDIO_MIMES = new Set([
  "audio/mpeg",
  "audio/wav",
  "audio/x-wav",
  "audio/ogg",
  "audio/webm",
  "audio/mp4",
  "audio/aac",
  "audio/flac",
  "audio/x-m4a",
]);

export const MAX_UPLOAD_BYTES = 200 * 1024 * 1024; // 200 MB

// ─── Standard REST calls (JSON) ───────────────────────────────────────────────

export async function apiListCalls(
  params: ListCallsParams = {},
): Promise<CallListOut> {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.page != null) qs.set("page", String(params.page));
  if (params.page_size != null) qs.set("page_size", String(params.page_size));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<CallListOut>(`/api/v1/calls/${query}`);
}

export async function apiGetCall(id: string): Promise<CallOut> {
  return apiFetch<CallOut>(`/api/v1/calls/${id}`);
}

export async function apiGetTranscript(id: string): Promise<TranscriptOut> {
  return apiFetch<TranscriptOut>(`/api/v1/calls/${id}/transcript`);
}

export async function apiDeleteCall(id: string): Promise<void> {
  await apiFetch<void>(`/api/v1/calls/${id}`, { method: "DELETE" });
}

// ─── Upload with XHR (for progress events) ────────────────────────────────────

export function apiUploadCall(
  file: File,
  onProgress?: (pct: number) => void,
): Promise<CallOut> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/calls/");

    const token = tokenStore.get();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status === 201) {
        resolve(JSON.parse(xhr.responseText) as CallOut);
      } else {
        let body: Record<string, unknown> = {};
        try {
          body = JSON.parse(xhr.responseText) as Record<string, unknown>;
        } catch {
          /* empty */
        }
        reject(new ApiError(xhr.status, body));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(form);
  });
}

// ─── Audio as blob URL (so Bearer token is sent) ─────────────────────────────

export async function fetchAudioObjectUrl(callId: string): Promise<string> {
  const token = tokenStore.get();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let resp = await fetch(`/api/v1/calls/${callId}/audio`, { headers });

  if (resp.status === 401 && token) {
    const refreshed = await apiRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${tokenStore.get()!}`;
      resp = await fetch(`/api/v1/calls/${callId}/audio`, { headers });
    }
  }

  if (!resp.ok) throw new ApiError(resp.status, {});
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}

// ─── SSE via fetch + ReadableStream (so Bearer token is sent) ────────────────

export async function subscribeCallEvents(
  callId: string,
  onEvent: (payload: SsePayload) => void,
  signal: AbortSignal,
): Promise<void> {
  const token = tokenStore.get();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let resp = await fetch(`/api/v1/calls/${callId}/events`, {
    headers,
    signal,
  });

  if (resp.status === 401 && token) {
    const refreshed = await apiRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${tokenStore.get()!}`;
      resp = await fetch(`/api/v1/calls/${callId}/events`, { headers, signal });
    }
  }

  if (!resp.ok || !resp.body) return;

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const payload = JSON.parse(line.slice(6)) as SsePayload;
            onEvent(payload);
          } catch {
            /* skip malformed SSE line */
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npm run typecheck
```

Expected: no errors in the new/modified files.

---

## Task 2 — `StatusBadge` component + `tailwind.config.ts` pulse keyframe

**Files:**
- Create: `frontend/src/components/calls/StatusBadge.tsx`
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Add `pulse-slow` keyframe to `tailwind.config.ts`**

Open `frontend/tailwind.config.ts`. In the `keyframes` object, add:

```ts
"pulse-slow": {
  "0%, 100%": { opacity: "1" },
  "50%": { opacity: "0.4" },
},
```

In the `animation` object, add:

```ts
"pulse-slow": "pulse-slow 2s ease-in-out infinite",
```

- [ ] **Step 2: Create `frontend/src/components/calls/StatusBadge.tsx`**

```tsx
import { cn } from "@/lib/utils";
import type { CallStatus } from "@/lib/api/calls";

interface StatusBadgeProps {
  status: CallStatus;
  className?: string;
}

const CONFIG: Record<
  CallStatus,
  { label: string; classes: string; pulse?: boolean }
> = {
  uploaded: {
    label: "Uploaded",
    classes: "bg-muted text-muted-foreground",
  },
  transcribing: {
    label: "Transcribing",
    classes: "bg-[hsl(var(--at-risk)/0.12)] text-[hsl(var(--at-risk))]",
    pulse: true,
  },
  diarizing: {
    label: "Diarizing",
    classes: "bg-[hsl(var(--at-risk)/0.12)] text-[hsl(var(--at-risk))]",
    pulse: true,
  },
  transcribed: {
    label: "Transcribed",
    classes: "bg-[hsl(var(--quality)/0.12)] text-[hsl(var(--quality))]",
  },
  failed: {
    label: "Failed",
    classes: "bg-[hsl(var(--fail)/0.12)] text-[hsl(var(--fail))]",
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const cfg = CONFIG[status] ?? CONFIG.uploaded;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
        cfg.classes,
        className,
      )}
    >
      {cfg.pulse && (
        <span className="h-1.5 w-1.5 animate-pulse-slow rounded-full bg-current" />
      )}
      {cfg.label}
    </span>
  );
}
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npm run typecheck
```

Expected: no errors.

---

## Task 3 — `CallStatusStepper` component + tests

**Files:**
- Create: `frontend/src/__tests__/CallStatusStepper.test.tsx`
- Create: `frontend/src/components/calls/CallStatusStepper.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/__tests__/CallStatusStepper.test.tsx`:

```tsx
import { render, screen, act, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SsePayload } from "@/lib/api/calls";

// ── Mock subscribeCallEvents so we control SSE events in tests ────────────────
let capturedOnEvent: ((p: SsePayload) => void) | null = null;
const mockSubscribe = vi.fn(
  (
    _id: string,
    onEvent: (p: SsePayload) => void,
    _signal: AbortSignal,
  ): Promise<void> => {
    capturedOnEvent = onEvent;
    return new Promise(() => {
      /* never resolves — test drives events manually */
    });
  },
);

vi.mock("@/lib/api/calls", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/calls")>();
  return { ...actual, subscribeCallEvents: mockSubscribe };
});

import { CallStatusStepper } from "@/components/calls/CallStatusStepper";

// ── Helpers ───────────────────────────────────────────────────────────────────

function sendEvent(payload: SsePayload) {
  act(() => {
    capturedOnEvent?.(payload);
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockSubscribe.mockClear();
  capturedOnEvent = null;
});
afterEach(() => vi.clearAllMocks());

describe("CallStatusStepper", () => {
  it("shows initial status immediately", () => {
    render(
      <CallStatusStepper callId="abc" initialStatus="transcribing" />,
    );
    expect(screen.getByText(/transcribing/i)).toBeInTheDocument();
  });

  it("advances status as SSE events arrive", async () => {
    render(<CallStatusStepper callId="abc" initialStatus="transcribing" />);

    sendEvent({ status: "diarizing" });
    await waitFor(() =>
      expect(screen.getByText(/diarizing/i)).toBeInTheDocument(),
    );
  });

  it("calls onComplete when transcribed event arrives", async () => {
    const onComplete = vi.fn();
    render(
      <CallStatusStepper
        callId="abc"
        initialStatus="transcribing"
        onComplete={onComplete}
      />,
    );

    sendEvent({ status: "transcribed" });
    await waitFor(() =>
      expect(onComplete).toHaveBeenCalledWith("transcribed"),
    );
  });

  it("shows error detail on failed event", async () => {
    render(<CallStatusStepper callId="abc" initialStatus="transcribing" />);

    sendEvent({ status: "failed", detail: "transcriber exploded" });
    await waitFor(() =>
      expect(screen.getByText(/transcriber exploded/i)).toBeInTheDocument(),
    );
  });

  it("does NOT subscribe when initial status is already terminal", () => {
    render(
      <CallStatusStepper callId="abc" initialStatus="transcribed" />,
    );
    expect(mockSubscribe).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL (component not yet created)**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "CallStatusStepper"
```

Expected: `Cannot find module '@/components/calls/CallStatusStepper'`.

- [ ] **Step 3: Create `frontend/src/components/calls/CallStatusStepper.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  type CallStatus,
  type SsePayload,
  isTerminalStatus,
  subscribeCallEvents,
} from "@/lib/api/calls";

const STEPS: CallStatus[] = [
  "uploaded",
  "transcribing",
  "diarizing",
  "transcribed",
];

interface CallStatusStepperProps {
  callId: string;
  initialStatus: CallStatus;
  onComplete?: (status: CallStatus) => void;
  className?: string;
}

export function CallStatusStepper({
  callId,
  initialStatus,
  onComplete,
  className,
}: CallStatusStepperProps) {
  const [status, setStatus] = useState<CallStatus>(initialStatus);
  const [detail, setDetail] = useState<string | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const handleEvent = useCallback((payload: SsePayload) => {
    const next = payload.status as CallStatus;
    setStatus(next);
    if (payload.detail) setDetail(payload.detail);
    if (isTerminalStatus(next)) {
      onCompleteRef.current?.(next);
    }
  }, []);

  useEffect(() => {
    if (isTerminalStatus(initialStatus)) {
      onCompleteRef.current?.(initialStatus);
      return;
    }
    const controller = new AbortController();
    void subscribeCallEvents(callId, handleEvent, controller.signal).catch(
      (e: unknown) => {
        if (e instanceof Error && e.name !== "AbortError") {
          console.error("SSE connection error", e);
        }
      },
    );
    return () => controller.abort();
  }, [callId, handleEvent, initialStatus]);

  const currentIdx = STEPS.indexOf(status === "failed" ? "transcribed" : status);
  const failed = status === "failed";

  return (
    <div className={cn("flex flex-col gap-4 rounded-lg border border-border bg-card p-6", className)}>
      <p className="text-sm font-medium text-foreground">
        {failed ? "Processing failed" : "Processing your recording…"}
      </p>

      {/* Step indicators */}
      <ol className="flex items-center gap-0">
        {STEPS.map((step, idx) => {
          const done = !failed && idx < currentIdx;
          const active = !failed && idx === currentIdx;
          const isFailed = failed && idx === currentIdx;

          return (
            <li key={step} className="flex flex-1 items-center">
              {/* Circle */}
              <div
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-colors",
                  done && "bg-[hsl(var(--quality))] text-white",
                  active && "animate-pulse-slow bg-primary text-primary-foreground",
                  isFailed && "bg-[hsl(var(--fail))] text-white",
                  !done && !active && !isFailed && "bg-muted text-muted-foreground",
                )}
                aria-current={active ? "step" : undefined}
              >
                {done ? "✓" : idx + 1}
              </div>
              {/* Label */}
              <span
                className={cn(
                  "ml-2 hidden text-xs font-medium sm:block",
                  (done || active) && !isFailed ? "text-foreground" : "text-muted-foreground",
                  isFailed && "text-[hsl(var(--fail))]",
                )}
              >
                {step}
              </span>
              {/* Connector */}
              {idx < STEPS.length - 1 && (
                <div
                  className={cn(
                    "mx-2 h-px flex-1 transition-colors",
                    done ? "bg-[hsl(var(--quality))]" : "bg-border",
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>

      {/* Error detail */}
      {failed && detail && (
        <p className="rounded-md bg-[hsl(var(--fail)/0.08)] px-3 py-2 text-xs text-[hsl(var(--fail))]">
          {detail}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "CallStatusStepper"
```

Expected: all 5 tests pass.

---

## Task 4 — `UploadDropzone` component + tests + upload page

**Files:**
- Create: `frontend/src/__tests__/UploadDropzone.test.tsx`
- Create: `frontend/src/components/calls/UploadDropzone.tsx`
- Create: `frontend/src/app/app/upload/page.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/__tests__/UploadDropzone.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CallOut } from "@/lib/api/calls";

// ── Mock API + router ─────────────────────────────────────────────────────────
const mockUpload = vi.fn();
vi.mock("@/lib/api/calls", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/calls")>();
  return { ...actual, apiUploadCall: mockUpload };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { UploadDropzone } from "@/components/calls/UploadDropzone";

const FAKE_CALL: CallOut = {
  id: "call-1",
  status: "uploaded",
  original_filename: "test.wav",
  duration_seconds: null,
  agent_id: null,
  status_detail: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeFile(name: string, type: string, sizeBytes = 1024): File {
  const blob = new Blob([new Uint8Array(sizeBytes)], { type });
  return new File([blob], name, { type });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => mockUpload.mockReset());
afterEach(() => vi.clearAllMocks());

describe("UploadDropzone", () => {
  it("renders the drop zone", () => {
    render(<UploadDropzone onUploaded={vi.fn()} />);
    expect(
      screen.getByText(/drag and drop|choose file/i),
    ).toBeInTheDocument();
  });

  it("rejects a non-audio file type", async () => {
    const user = userEvent.setup();
    render(<UploadDropzone onUploaded={vi.fn()} />);

    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await user.upload(input, makeFile("doc.pdf", "application/pdf"));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/audio/i),
    );
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it("rejects an oversized file", async () => {
    const user = userEvent.setup();
    render(<UploadDropzone onUploaded={vi.fn()} />);

    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    // MAX_UPLOAD_BYTES = 200 MB; we fake a large file by overriding .size
    const bigFile = makeFile("big.wav", "audio/wav");
    Object.defineProperty(bigFile, "size", { value: 210 * 1024 * 1024 });
    await user.upload(input, bigFile);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/200 MB/i),
    );
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it("calls apiUploadCall and invokes onUploaded on valid WAV", async () => {
    mockUpload.mockResolvedValueOnce(FAKE_CALL);
    const onUploaded = vi.fn();
    const user = userEvent.setup();
    render(<UploadDropzone onUploaded={onUploaded} />);

    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await user.upload(input, makeFile("call.wav", "audio/wav"));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(FAKE_CALL));
    expect(mockUpload).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "UploadDropzone"
```

Expected: `Cannot find module '@/components/calls/UploadDropzone'`.

- [ ] **Step 3: Create `frontend/src/components/calls/UploadDropzone.tsx`**

```tsx
"use client";

import { useCallback, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  ALLOWED_AUDIO_MIMES,
  MAX_UPLOAD_BYTES,
  apiUploadCall,
  type CallOut,
} from "@/lib/api/calls";
import { ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

interface UploadDropzoneProps {
  onUploaded: (call: CallOut) => void;
  className?: string;
}

export function UploadDropzone({ onUploaded, className }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const validate = useCallback((file: File): string | null => {
    if (!ALLOWED_AUDIO_MIMES.has(file.type)) {
      return `Unsupported file type "${file.type}". Please upload an audio file (MP3, WAV, OGG, etc.).`;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return `File exceeds the maximum allowed size of 200 MB.`;
    }
    return null;
  }, []);

  const upload = useCallback(
    async (file: File) => {
      const err = validate(file);
      if (err) {
        setError(err);
        return;
      }
      setError(null);
      setProgress(0);
      try {
        const call = await apiUploadCall(file, setProgress);
        setProgress(null);
        onUploaded(call);
      } catch (e) {
        setProgress(null);
        if (e instanceof ApiError) {
          const msg =
            (e.body.message as string | undefined) ??
            "Upload failed. Please try again.";
          setError(msg);
        } else {
          setError("Upload failed. Please try again.");
        }
      }
    },
    [validate, onUploaded],
  );

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    // Reset so the same file can be re-selected after an error
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void upload(file);
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-border bg-muted/30 px-8 py-14 text-center transition-colors",
          isDragOver && "border-primary bg-primary/5",
          progress != null && "pointer-events-none opacity-70",
        )}
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/50">
          <span className="text-3xl text-muted-foreground">♬</span>
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">
            Drag and drop your recording here
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            or{" "}
            <span className="text-primary underline-offset-2 hover:underline">
              choose file
            </span>{" "}
            · MP3, WAV, OGG, FLAC up to 200 MB
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="audio/*"
          className="sr-only"
          onChange={handleFileChange}
        />
      </div>

      {/* Upload progress */}
      {progress != null && (
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Uploading…</span>
            <span className="tabular">{progress}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-150"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Validation / server error */}
      {error && (
        <p role="alert" className="text-sm text-[hsl(var(--fail))]">
          {error}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/app/app/upload/page.tsx`**

```tsx
"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import type { CallOut } from "@/lib/api/calls";
import { isTerminalStatus } from "@/lib/api/calls";
import { CallStatusStepper } from "@/components/calls/CallStatusStepper";
import { UploadDropzone } from "@/components/calls/UploadDropzone";

export default function UploadPage() {
  const router = useRouter();
  const [uploadedCall, setUploadedCall] = useState<CallOut | null>(null);

  const handleUploaded = useCallback((call: CallOut) => {
    setUploadedCall(call);
    // If somehow already terminal (shouldn't be for 'uploaded' status)
    if (isTerminalStatus(call.status)) {
      router.push(`/app/calls/${call.id}`);
    }
  }, [router]);

  const handleComplete = useCallback(
    (status: string) => {
      if (status === "transcribed" && uploadedCall) {
        router.push(`/app/calls/${uploadedCall.id}`);
      }
    },
    [router, uploadedCall],
  );

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-8 pt-8">
      <div>
        <h1 className="font-display text-2xl font-bold text-foreground">
          Upload recording
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          CallLens will transcribe and analyse the call automatically.
        </p>
      </div>

      {uploadedCall ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Uploaded{" "}
            <span className="font-medium text-foreground">
              {uploadedCall.original_filename}
            </span>
            . Processing now…
          </p>
          <CallStatusStepper
            callId={uploadedCall.id}
            initialStatus={uploadedCall.status}
            onComplete={handleComplete}
          />
        </div>
      ) : (
        <UploadDropzone onUploaded={handleUploaded} />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "UploadDropzone"
```

Expected: all 4 tests pass.

---

## Task 5 — Calls list page + tests

**Files:**
- Create: `frontend/src/__tests__/CallsListPage.test.tsx`
- Create: `frontend/src/app/app/calls/page.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/__tests__/CallsListPage.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CallListOut } from "@/lib/api/calls";

// ── Mocks ──────────────────────────────────────────────────────────────────────
const mockListCalls = vi.fn();
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
    expect(screen.getByText("Transcribed")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "CallsPage"
```

Expected: `Cannot find module '@/app/app/calls/page'`.

- [ ] **Step 3: Create `frontend/src/app/app/calls/page.tsx`**

```tsx
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  apiListCalls,
  type CallOut,
  type CallStatus,
} from "@/lib/api/calls";
import { StatusBadge } from "@/components/calls/StatusBadge";
import { Button } from "@/components/ui/button";
import { cn, formatDuration, formatRelative } from "@/lib/utils";

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "uploaded", label: "Uploaded" },
  { value: "transcribing", label: "Transcribing" },
  { value: "diarizing", label: "Diarizing" },
  { value: "transcribed", label: "Transcribed" },
  { value: "failed", label: "Failed" },
];

export default function CallsPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["calls", { status: statusFilter, page }],
    queryFn: () =>
      apiListCalls({
        status: statusFilter || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="flex flex-col gap-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-foreground">
          Calls
        </h1>
        <Button onClick={() => router.push("/app/upload")}>
          + Upload recording
        </Button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {data && (
          <span className="text-sm text-muted-foreground">
            {data.total} call{data.total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="flex flex-col gap-2">
          {[...Array<null>(5)].map((_, i) => (
            <div
              key={i}
              className="h-14 animate-pulse rounded-lg bg-muted"
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && data?.items.length === 0 && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/50">
            <span className="font-display text-3xl text-muted-foreground/50">
              ◎
            </span>
          </div>
          <div>
            <p className="font-medium text-foreground">No calls yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Upload your first recording to get started.
            </p>
          </div>
          <Button onClick={() => router.push("/app/upload")}>
            Upload recording
          </Button>
        </div>
      )}

      {/* Table */}
      {!isLoading && data && data.items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                  File
                </th>
                <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                  Status
                </th>
                <th className="px-4 py-3 text-right font-semibold text-muted-foreground tabular">
                  Duration
                </th>
                <th className="px-4 py-3 text-right font-semibold text-muted-foreground">
                  Uploaded
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((call: CallOut, idx) => (
                <tr
                  key={call.id}
                  className={cn(
                    "transition-colors hover:bg-muted/30",
                    idx < data.items.length - 1 && "border-b border-border",
                  )}
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/app/calls/${call.id}`}
                      className="font-medium text-foreground hover:text-primary hover:underline"
                    >
                      {call.original_filename}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={call.status as CallStatus} />
                  </td>
                  <td className="px-4 py-3 text-right tabular text-muted-foreground">
                    {formatDuration(call.duration_seconds)}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {formatRelative(call.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            ← Previous
          </Button>
          <span className="text-sm text-muted-foreground tabular">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "CallsPage"
```

Expected: all 4 tests pass.

---

## Task 6 — `AudioPlayer` + `TranscriptPanel` components + tests

**Files:**
- Create: `frontend/src/__tests__/TranscriptPanel.test.tsx`
- Create: `frontend/src/components/calls/AudioPlayer.tsx`
- Create: `frontend/src/components/calls/TranscriptPanel.tsx`

- [ ] **Step 1: Write failing tests for TranscriptPanel**

Create `frontend/src/__tests__/TranscriptPanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SegmentOut } from "@/lib/api/calls";
import { TranscriptPanel } from "@/components/calls/TranscriptPanel";

const SEGMENTS: SegmentOut[] = [
  {
    id: "s1",
    sequence: 0,
    start_ms: 0,
    end_ms: 4000,
    text: "Hello there",
    speaker: "agent",
  },
  {
    id: "s2",
    sequence: 1,
    start_ms: 4500,
    end_ms: 9000,
    text: "Hi how can I help",
    speaker: "customer",
  },
  {
    id: "s3",
    sequence: 2,
    start_ms: 9500,
    end_ms: 14000,
    text: "I have a question",
    speaker: "agent",
  },
];

describe("TranscriptPanel", () => {
  it("renders all segment texts", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );
    expect(screen.getByText("Hello there")).toBeInTheDocument();
    expect(screen.getByText("Hi how can I help")).toBeInTheDocument();
    expect(screen.getByText("I have a question")).toBeInTheDocument();
  });

  it("clicking a segment calls onSeek with the segment start_ms", async () => {
    const onSeek = vi.fn();
    const user = userEvent.setup();
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={0}
        onSeek={onSeek}
      />,
    );
    await user.click(screen.getByText("Hi how can I help"));
    expect(onSeek).toHaveBeenCalledWith(4500);
  });

  it("marks the active segment with data-active when currentTimeSec matches", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={5}  // 5s falls in segment 2 (4.5s–9s)
        onSeek={vi.fn()}
      />,
    );
    const activeEl = document.querySelector("[data-active]");
    expect(activeEl).not.toBeNull();
    expect(activeEl).toHaveTextContent("Hi how can I help");
  });

  it("shows no active segment when currentTimeSec is before the first segment", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={-1}
        onSeek={vi.fn()}
      />,
    );
    expect(document.querySelector("[data-active]")).toBeNull();
  });

  it("displays speaker labels visually distinguished", () => {
    render(
      <TranscriptPanel
        segments={SEGMENTS}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );
    const agentLabels = screen.getAllByText("agent");
    const customerLabels = screen.getAllByText("customer");
    expect(agentLabels.length).toBeGreaterThan(0);
    expect(customerLabels.length).toBeGreaterThan(0);
  });

  it("shows empty-state message when segments array is empty", () => {
    render(
      <TranscriptPanel
        segments={[]}
        currentTimeSec={0}
        onSeek={vi.fn()}
      />,
    );
    expect(screen.getByText(/no transcript/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "TranscriptPanel"
```

Expected: `Cannot find module '@/components/calls/TranscriptPanel'`.

- [ ] **Step 3: Create `frontend/src/components/calls/AudioPlayer.tsx`**

```tsx
"use client";

import { useEffect, useImperativeHandle, useRef, useState } from "react";
import { cn, formatDuration } from "@/lib/utils";

export interface AudioPlayerRef {
  seekTo: (seconds: number) => void;
}

interface AudioPlayerProps {
  src: string;
  onTimeUpdate?: (seconds: number) => void;
  className?: string;
  ref?: React.Ref<AudioPlayerRef>;
}

export function AudioPlayer({
  src,
  onTimeUpdate,
  className,
  ref,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [rate, setRate] = useState(1);

  useImperativeHandle(ref, () => ({
    seekTo: (seconds: number) => {
      if (audioRef.current) audioRef.current.currentTime = seconds;
    },
  }));

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = rate;
  }, [rate]);

  function handleTimeUpdate() {
    const t = audioRef.current?.currentTime ?? 0;
    setCurrentTime(t);
    onTimeUpdate?.(t);
  }

  function togglePlay() {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      void audioRef.current.play();
    }
  }

  function handleSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const t = parseFloat(e.target.value);
    if (audioRef.current) audioRef.current.currentTime = t;
    setCurrentTime(t);
    onTimeUpdate?.(t);
  }

  const RATES = [1, 1.5, 2] as const;

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border bg-card p-4",
        className,
      )}
    >
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={() =>
          setDuration(audioRef.current?.duration ?? 0)
        }
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />

      {/* Progress row */}
      <div className="flex items-center gap-3">
        <button
          onClick={togglePlay}
          aria-label={isPlaying ? "Pause" : "Play"}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm text-primary-foreground transition-transform hover:scale-105 active:scale-95"
        >
          {isPlaying ? "⏸" : "▶"}
        </button>

        <input
          type="range"
          min={0}
          max={duration || 1}
          step={0.1}
          value={currentTime}
          onChange={handleSeek}
          aria-label="Audio progress"
          className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-muted accent-primary"
        />

        <span className="tabular shrink-0 text-xs text-muted-foreground">
          {formatDuration(currentTime)} /{" "}
          {duration ? formatDuration(duration) : "--:--"}
        </span>
      </div>

      {/* Playback rate */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground">Speed</span>
        {RATES.map((r) => (
          <button
            key={r}
            onClick={() => setRate(r)}
            className={cn(
              "rounded px-2 py-0.5 text-xs font-medium tabular transition-colors",
              rate === r
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            {r}×
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/calls/TranscriptPanel.tsx`**

```tsx
"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { SegmentOut } from "@/lib/api/calls";

interface TranscriptPanelProps {
  segments: SegmentOut[];
  currentTimeSec: number;
  onSeek: (ms: number) => void;
  className?: string;
}

function formatMs(ms: number): string {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function TranscriptPanel({
  segments,
  currentTimeSec,
  onSeek,
  className,
}: TranscriptPanelProps) {
  // Find the last segment whose start is <= currentTimeSec
  let activeIdx = -1;
  for (let i = 0; i < segments.length; i++) {
    if (segments[i].start_ms / 1000 <= currentTimeSec) {
      activeIdx = i;
    }
  }

  const activeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [activeIdx]);

  if (segments.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center justify-center py-12 text-sm text-muted-foreground",
          className,
        )}
      >
        No transcript available yet.
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col overflow-auto rounded-lg border border-border bg-card",
        className,
      )}
    >
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">Transcript</h3>
      </div>

      <div className="flex flex-col p-2">
        {segments.map((seg, idx) => {
          const isActive = idx === activeIdx;

          return (
            <button
              key={seg.id}
              ref={isActive ? activeRef : null}
              data-active={isActive || undefined}
              onClick={() => onSeek(seg.start_ms)}
              className={cn(
                "flex gap-3 rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted/50",
                isActive && "bg-primary/5 ring-1 ring-inset ring-primary/20",
              )}
            >
              {/* Timestamp */}
              <span className="tabular shrink-0 pt-0.5 text-[11px] text-muted-foreground">
                {formatMs(seg.start_ms)}
              </span>

              {/* Speaker + text */}
              <div className="flex flex-1 flex-col gap-0.5">
                <span
                  className={cn(
                    "text-[10px] font-bold uppercase tracking-wider",
                    seg.speaker === "agent" && "text-primary",
                    seg.speaker === "customer" &&
                      "text-[hsl(var(--at-risk))]",
                    seg.speaker === "unknown" && "text-muted-foreground",
                  )}
                >
                  {seg.speaker}
                </span>
                <p className="text-sm leading-relaxed text-foreground">
                  {seg.text}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 "TranscriptPanel"
```

Expected: all 6 tests pass.

---

## Task 7 — Call detail page

**Files:**
- Create: `frontend/src/app/app/calls/[id]/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/app/calls/[id]/page.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiDeleteCall,
  apiGetCall,
  apiGetTranscript,
  fetchAudioObjectUrl,
  isTerminalStatus,
  type CallOut,
  type CallStatus,
} from "@/lib/api/calls";
import { StatusBadge } from "@/components/calls/StatusBadge";
import { CallStatusStepper } from "@/components/calls/CallStatusStepper";
import { AudioPlayer, type AudioPlayerRef } from "@/components/calls/AudioPlayer";
import { TranscriptPanel } from "@/components/calls/TranscriptPanel";
import { Button } from "@/components/ui/button";
import { formatDuration, formatRelative } from "@/lib/utils";

export default function CallDetailPage() {
  const params = useParams<{ id: string }>();
  const callId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const audioPlayerRef = useRef<AudioPlayerRef>(null);
  const [currentTimeSec, setCurrentTimeSec] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data: call, isLoading } = useQuery<CallOut>({
    queryKey: ["call", callId],
    queryFn: () => apiGetCall(callId),
    enabled: !!callId,
  });

  const terminal = call ? isTerminalStatus(call.status as CallStatus) : false;
  const transcribed = call?.status === "transcribed";

  const { data: transcript } = useQuery({
    queryKey: ["call-transcript", callId],
    queryFn: () => apiGetTranscript(callId),
    enabled: transcribed,
  });

  // Fetch audio blob URL when call is transcribed
  useEffect(() => {
    if (!transcribed || audioUrl) return;
    fetchAudioObjectUrl(callId)
      .then((url) => setAudioUrl(url))
      .catch(console.error);
  }, [transcribed, callId, audioUrl]);

  // Revoke blob URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  // When SSE stepper completes, invalidate and re-fetch the call
  const handleStepperComplete = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["call", callId] });
    await queryClient.invalidateQueries({ queryKey: ["calls"] });
  }, [callId, queryClient]);

  const handleSeek = useCallback((ms: number) => {
    audioPlayerRef.current?.seekTo(ms / 1000);
  }, []);

  async function handleDelete() {
    setIsDeleting(true);
    try {
      await apiDeleteCall(callId);
      router.push("/app/calls");
    } catch {
      setIsDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!call) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <p className="text-muted-foreground">Call not found.</p>
        <Button variant="outline" onClick={() => router.push("/app/calls")}>
          Back to calls
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push("/app/calls")}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              ← Calls
            </button>
          </div>
          <h1 className="font-display text-xl font-bold text-foreground">
            {call.original_filename}
          </h1>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <StatusBadge status={call.status as CallStatus} />
            {call.duration_seconds != null && (
              <span className="tabular">{formatDuration(call.duration_seconds)}</span>
            )}
            <span>{formatRelative(call.created_at)}</span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled>
            Export to CRM
          </Button>

          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Delete this call?</span>
              <Button
                variant="destructive"
                size="sm"
                disabled={isDeleting}
                onClick={handleDelete}
              >
                {isDeleting ? "Deleting…" : "Yes, delete"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmDelete(false)}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmDelete(true)}
            >
              Delete
            </Button>
          )}
        </div>
      </div>

      {/* ── Processing state: live stepper ── */}
      {!terminal && (
        <CallStatusStepper
          callId={callId}
          initialStatus={call.status as CallStatus}
          onComplete={handleStepperComplete}
        />
      )}

      {/* ── Audio player (once transcribed + blob ready) ── */}
      {transcribed && audioUrl && (
        <AudioPlayer
          ref={audioPlayerRef}
          src={audioUrl}
          onTimeUpdate={setCurrentTimeSec}
        />
      )}

      {/* ── Transcript panel ── */}
      {transcribed && (
        <TranscriptPanel
          segments={transcript?.segments ?? []}
          currentTimeSec={currentTimeSec}
          onSeek={handleSeek}
          className="max-h-[60vh]"
        />
      )}

      {/* ── Failed state detail ── */}
      {call.status === "failed" && call.status_detail && (
        <div className="rounded-lg border border-[hsl(var(--fail)/0.3)] bg-[hsl(var(--fail)/0.06)] p-4 text-sm text-[hsl(var(--fail))]">
          <p className="font-semibold">Processing failed</p>
          <p className="mt-1">{call.status_detail}</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npm run typecheck
```

Expected: no new errors.

---

## Task 8 — App shell updates

**Files:**
- Modify: `frontend/src/app/app/page.tsx`
- Modify: `frontend/src/components/app/Sidebar.tsx`
- Modify: `frontend/src/components/app/TopBar.tsx`

- [ ] **Step 1: Replace `/app` landing page with a server-side redirect**

Replace the full content of `frontend/src/app/app/page.tsx` with:

```tsx
import { redirect } from "next/navigation";

export default function AppPage() {
  redirect("/app/calls");
}
```

- [ ] **Step 2: Update Sidebar — remove `placeholder` from Calls, activate Upload**

Open `frontend/src/components/app/Sidebar.tsx`. Replace the `navItems` array:

```ts
const navItems = [
  { label: "Calls", href: "/app/calls", icon: "◎" },
  { label: "Upload", href: "/app/upload", icon: "↑" },
  { label: "Agents", href: "/app/agents", icon: "↗", placeholder: true },
  { label: "Teams", href: "/app/teams", icon: "⊛", placeholder: true },
  { label: "Rubrics", href: "/app/rubrics", icon: "◻", placeholder: true },
  { label: "Search", href: "/app/search", icon: "⌕", placeholder: true },
  { label: "Settings", href: "/app/settings", icon: "⌇", placeholder: true },
];
```

Also update the `isActive` check so `/app/calls/[id]` also highlights the Calls item:

```ts
const isActive =
  href === "/app/calls"
    ? pathname.startsWith("/app/calls")
    : href === "/app/upload"
      ? pathname === "/app/upload"
      : pathname === href;
```

Replace the `isActive` line inside the `.map()` with the above expression.

- [ ] **Step 3: Add "Upload recording" button to TopBar**

Open `frontend/src/components/app/TopBar.tsx`. At the top, add:

```ts
import Link from "next/link";
```

In the JSX, replace `<div />` (the left spacer) with:

```tsx
<Link
  href="/app/upload"
  className="inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
>
  + Upload recording
</Link>
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd frontend && npm run typecheck
```

Expected: no errors.

---

## Task 9 — All checks + `BUILD_LOG.md` + single commit

**Files:**
- Modify: `docs/BUILD_LOG.md`

- [ ] **Step 1: Run ESLint**

```bash
cd frontend && npm run lint
```

Fix any errors before proceeding.

- [ ] **Step 2: Run TypeScript type-check**

```bash
cd frontend && npm run typecheck
```

Expected: 0 errors.

- [ ] **Step 3: Run full test suite**

```bash
cd frontend && npm test
```

Expected: all tests pass (existing 16 + new 19 = 35+).

- [ ] **Step 4: Run backend tests to confirm no regressions**

```bash
cd /Users/kusalsaraf/Desktop/CallLens/backend && uv run pytest tests/ -q
```

Expected: 34 passed.

- [ ] **Step 5: Update `docs/BUILD_LOG.md`**

Add a new row to the table:

```markdown
| 2B | done | TBD | 2026-06-07 | Upload page (drag-and-drop, XHR progress, SSE stepper), calls list (table, filters, pagination), call detail (audio player + two-way transcript sync via blob URL + fetch SSE) |
```

- [ ] **Step 6: Set git identity and commit everything**

```bash
git config user.name "Kusal Saraf"
git config user.email "kusalsaraf5@gmail.com"
```

Stage all changed and new frontend files plus BUILD_LOG:

```bash
cd /Users/kusalsaraf/Desktop/CallLens && git add \
  frontend/src/lib/api/client.ts \
  frontend/src/lib/api/calls.ts \
  frontend/src/lib/utils.ts \
  frontend/src/components/calls/ \
  frontend/src/app/app/page.tsx \
  frontend/src/app/app/upload/ \
  frontend/src/app/app/calls/ \
  frontend/src/components/app/Sidebar.tsx \
  frontend/src/components/app/TopBar.tsx \
  frontend/src/__tests__/CallStatusStepper.test.tsx \
  frontend/src/__tests__/UploadDropzone.test.tsx \
  frontend/src/__tests__/CallsListPage.test.tsx \
  frontend/src/__tests__/TranscriptPanel.test.tsx \
  frontend/tailwind.config.ts \
  docs/BUILD_LOG.md
```

```bash
git commit -m "feat(web): call upload with live progress, calls list, and call detail with synced transcript"
```

---

## Self-Review Checklist

### Spec coverage
- [x] Drag-and-drop + file-picker dropzone → `UploadDropzone`
- [x] Client-side validation (audio MIME + max size) → `UploadDropzone`
- [x] POST multipart to `/api/v1/calls` → `apiUploadCall` (XHR with progress)
- [x] Upload % progress → XHR `upload.onprogress` + progress bar UI
- [x] SSE via authed fetch (not EventSource) → `subscribeCallEvents`
- [x] Live status stepper uploaded→transcribing→diarizing→transcribed → `CallStatusStepper`
- [x] On terminal status invalidate queries → `handleStepperComplete`
- [x] On failed: show error detail → `CallStatusStepper` + detail section in detail page
- [x] Calls list: filename, duration (mm:ss tabular), uploaded-at (relative), status badge → `CallsPage`
- [x] Status badge semantic colours + pulse for in-progress → `StatusBadge`
- [x] Row click → detail → `<Link>` on filename
- [x] Status filter + pagination → `CallsPage`
- [x] Calls as default landing tab → `/app/page.tsx` redirect
- [x] Call detail header: filename, status, duration, uploaded-at → `CallDetailPage`
- [x] Delete action (inline confirm → DELETE → back to list) → `CallDetailPage`
- [x] Disabled "Export to CRM" → `CallDetailPage`
- [x] Live stepper while processing → `CallDetailPage`
- [x] Audio player: play/pause, seek, time display (tabular), playback rate → `AudioPlayer`
- [x] Audio via blob URL (token sent in header) → `fetchAudioObjectUrl`
- [x] Transcript panel: speaker labels, timestamps, click-to-seek → `TranscriptPanel`
- [x] Active segment highlight + auto-scroll as audio plays → `TranscriptPanel`
- [x] Two-way sync via `audioPlayerRef.seekTo` + `currentTimeSec` prop → `CallDetailPage`
- [x] Single-speaker (NullDiarizer) graceful: `unknown` speaker shown in muted colour → `TranscriptPanel`
- [x] Tests: dropzone validation + submit → `UploadDropzone.test.tsx`
- [x] Tests: SSE stepper advances + completion → `CallStatusStepper.test.tsx`
- [x] Tests: list rows + badges + links → `CallsListPage.test.tsx`
- [x] Tests: segment click seeks; active segment highlighted → `TranscriptPanel.test.tsx`
- [x] No new npm packages added

### Type consistency
- `CallStatus` type is defined in `calls.ts` and imported everywhere
- `AudioPlayerRef.seekTo` takes `seconds: number` (not ms); `TranscriptPanel.onSeek` takes `ms: number` — conversion happens in `CallDetailPage.handleSeek`
- `SegmentOut.start_ms` is in milliseconds throughout
- `formatDuration` takes `seconds: number | null | undefined` everywhere it's called
