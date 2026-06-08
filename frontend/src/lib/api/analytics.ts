"use client";

import { apiFetch } from "./client";

// ─── Shared filter set ────────────────────────────────────────────────────────

export interface AnalyticsFilters {
  date_from?: string; // ISO-8601
  date_to?: string;
  team_id?: string;
  agent_id?: string;
}

function filtersToQs(f: AnalyticsFilters, extra?: Record<string, string>): string {
  const p = new URLSearchParams();
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  if (f.team_id) p.set("team_id", f.team_id);
  if (f.agent_id) p.set("agent_id", f.agent_id);
  if (extra) Object.entries(extra).forEach(([k, v]) => p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

// ─── Response types ───────────────────────────────────────────────────────────

export interface OverviewOut {
  calls_total: number;
  calls_scored: number;
  avg_overall_score: number | null;
  compliance_pass_rate: number | null;
  flagged_count: number;
}

export interface QualityBucketOut {
  date: string;
  avg_overall_score: number;
  calls_scored: number;
}

export interface QualityTrendsOut {
  bucket: string;
  items: QualityBucketOut[];
}

export interface ScoreBucketOut {
  bucket: number;
  label: string;
  count: number;
}

export interface BandDistributionOut {
  quality: number;
  at_risk: number;
  fail: number;
}

export interface ScoreDistributionOut {
  buckets: ScoreBucketOut[];
  bands: BandDistributionOut;
}

export interface ComplianceTrendPointOut {
  date: string;
  pass_rate: number;
  calls: number;
}

export interface ComplianceOut {
  pass_rate: number | null;
  trend: ComplianceTrendPointOut[];
}

export interface FlaggedCallOut {
  call_id: string;
  agent_name: string | null;
  overall_score: number;
  band: string;
  escalate_for_review: boolean;
  escalation_reason: string | null;
  uploaded_at: string;
}

export interface FlaggedListOut {
  items: FlaggedCallOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface LeaderboardEntryOut {
  agent_id: string;
  name: string;
  team: string;
  calls_scored: number;
  avg_overall_score: number;
  compliance_pass_rate: number;
  is_at_risk: boolean;
}

export interface LeaderboardOut {
  items: LeaderboardEntryOut[];
}

export interface TeamOut {
  id: string;
  name: string;
}

export interface TeamListOut {
  items: TeamOut[];
}

// ─── Fetchers ─────────────────────────────────────────────────────────────────

export async function apiGetOverview(f: AnalyticsFilters): Promise<OverviewOut> {
  return apiFetch<OverviewOut>(`/api/v1/analytics/overview${filtersToQs(f)}`);
}

export async function apiGetQualityTrends(
  f: AnalyticsFilters,
  bucket: "day" | "week",
): Promise<QualityTrendsOut> {
  return apiFetch<QualityTrendsOut>(
    `/api/v1/analytics/quality-trends${filtersToQs(f, { bucket })}`,
  );
}

export async function apiGetScoreDistribution(
  f: AnalyticsFilters,
): Promise<ScoreDistributionOut> {
  return apiFetch<ScoreDistributionOut>(
    `/api/v1/analytics/score-distribution${filtersToQs(f)}`,
  );
}

export async function apiGetCompliance(f: AnalyticsFilters): Promise<ComplianceOut> {
  return apiFetch<ComplianceOut>(`/api/v1/analytics/compliance${filtersToQs(f)}`);
}

export async function apiGetFlagged(
  f: AnalyticsFilters,
  limit: number,
  offset: number,
): Promise<FlaggedListOut> {
  return apiFetch<FlaggedListOut>(
    `/api/v1/analytics/flagged${filtersToQs(f, { limit: String(limit), offset: String(offset) })}`,
  );
}

export async function apiGetLeaderboard(f: AnalyticsFilters): Promise<LeaderboardOut> {
  return apiFetch<LeaderboardOut>(`/api/v1/analytics/leaderboard${filtersToQs(f)}`);
}

export async function apiListTeams(): Promise<TeamListOut> {
  return apiFetch<TeamListOut>(`/api/v1/teams/`);
}
