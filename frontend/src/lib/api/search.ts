"use client";

import { apiFetch } from "./client";

// ─── Types (mirror Phase 7A backend response) ────────────────────────────────

export interface SegmentSnippet {
  segment_id: string;
  start_ms: number;
  text: string;
  similarity: number;
}

export interface SearchHit {
  call_id: string;
  agent_name: string | null;
  overall_score: number | null;
  band: string | null;
  uploaded_at: string | null;
  snippets: SegmentSnippet[];
}

export interface SearchResponse {
  query: string;
  results: SearchHit[];
  total: number;
}

export interface SearchParams {
  q: string;
  limit?: number;
  agent_id?: string;
  team_id?: string;
  date_from?: string;
  date_to?: string;
}

// ─── Fetcher ──────────────────────────────────────────────────────────────────

export async function apiSearch(params: SearchParams): Promise<SearchResponse> {
  const qs = new URLSearchParams();
  qs.set("q", params.q);
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.agent_id) qs.set("agent_id", params.agent_id);
  if (params.team_id) qs.set("team_id", params.team_id);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  return apiFetch<SearchResponse>(`/api/v1/search?${qs.toString()}`);
}
