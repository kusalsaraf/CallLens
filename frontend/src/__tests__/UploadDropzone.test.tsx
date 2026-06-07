import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CallOut } from "@/lib/api/calls";

// ── Mock API + router ─────────────────────────────────────────────────────────
const { mockUpload } = vi.hoisted(() => ({ mockUpload: vi.fn() }));
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

/** Fire a file change directly, bypassing userEvent's accept-attribute filter. */
function uploadViaFireEvent(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, "files", {
    value: [file],
    configurable: true,
  });
  fireEvent.change(input);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => mockUpload.mockReset());
afterEach(() => vi.clearAllMocks());

describe("UploadDropzone", () => {
  it("renders the drop zone", () => {
    render(<UploadDropzone onUploaded={vi.fn()} />);
    // Component renders "Drag and drop your recording here" — unique text
    expect(screen.getByText(/drag and drop your recording/i)).toBeInTheDocument();
  });

  it("rejects a non-audio file type", async () => {
    render(<UploadDropzone onUploaded={vi.fn()} />);
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;

    // fireEvent bypasses accept-attribute filtering in userEvent
    uploadViaFireEvent(input, makeFile("doc.pdf", "application/pdf"));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/audio/i),
    );
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it("rejects an oversized file", async () => {
    render(<UploadDropzone onUploaded={vi.fn()} />);
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;

    const bigFile = makeFile("big.wav", "audio/wav");
    Object.defineProperty(bigFile, "size", { value: 210 * 1024 * 1024 });
    uploadViaFireEvent(input, bigFile);

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
