"use client";

import { apiFetch } from "./client";
import type { AnalyticsFilters } from "./analytics";

// ─── Response types ───────────────────────────────────────────────────────────

export interface TopicAnalyticsEntry {
  topic_id: string;
  name: string;
  slug: string;
  call_count: number;
  avg_overall_score: number | null;
  band: string | null;
  flagged_rate: number | null;
}

export interface TopicAnalyticsOut {
  items: TopicAnalyticsEntry[];
}

export interface TopicOut {
  id: string;
  name: string;
  slug: string;
  keywords: string[];
}

export interface TopicListOut {
  items: TopicOut[];
}

export interface TopicDetailOut {
  id: string;
  name: string;
  slug: string;
  keywords: string[];
  call_count: number;
  avg_overall_score: number | null;
  band: string | null;
}

// ─── Fetchers ─────────────────────────────────────────────────────────────────

function filtersToQs(f: AnalyticsFilters): string {
  const p = new URLSearchParams();
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  if (f.team_id) p.set("team_id", f.team_id);
  if (f.agent_id) p.set("agent_id", f.agent_id);
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function apiGetTopicAnalytics(
  f: AnalyticsFilters,
): Promise<TopicAnalyticsOut> {
  return apiFetch<TopicAnalyticsOut>(
    `/api/v1/analytics/topics${filtersToQs(f)}`,
  );
}

export async function apiListTopics(): Promise<TopicListOut> {
  return apiFetch<TopicListOut>("/api/v1/topics/");
}

export async function apiGetTopic(id: string): Promise<TopicDetailOut> {
  return apiFetch<TopicDetailOut>(`/api/v1/topics/${id}`);
}
