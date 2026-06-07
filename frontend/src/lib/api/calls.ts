"use client";

import { ApiError, apiFetch, tokenStore } from "./client";
import { apiRefresh } from "./auth";

// ─── Types ────────────────────────────────────────────────────────────────────

export type CallStatus =
  | "uploaded"
  | "transcribing"
  | "diarizing"
  | "transcribed"
  | "scoring"
  | "scored"
  | "failed";

export const TERMINAL_STATUSES = new Set<CallStatus>([
  "transcribed", // kept for backward compat — calls may stop here if scoring not run
  "scored",       // happy-path terminal after scoring
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

export interface EvidenceOut {
  id: string;
  segment_id: string | null;
  quote: string;
}

export interface DimensionInfo {
  id: string;
  key: string;
  name: string;
  weight: number;
}

export interface CallScoreOut {
  id: string;
  dimension: DimensionInfo;
  score: number;
  confidence: number;
  rationale: string;
  is_supported: boolean;
  scored_at: string;
  evidence: EvidenceOut[];
}

export interface ScoresListOut {
  call_id: string;
  scores: CallScoreOut[];
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

export async function apiGetScores(callId: string): Promise<ScoresListOut> {
  return apiFetch<ScoresListOut>(`/api/v1/calls/${callId}/scores`);
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
