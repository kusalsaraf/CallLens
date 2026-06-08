"use client";

import { apiFetch } from "./client";

// ─── Team analytics types ─────────────────────────────────────────────────────

export interface TeamScoreBandOut {
  quality: number;
  at_risk: number;
  fail: number;
}

export interface TeamAgentComparisonOut {
  agent_id: string;
  name: string;
  calls_scored: number;
  avg_overall_score: number;
}

export interface TeamAnalyticsOut {
  calls_scored: number;
  avg_overall_score: number | null;
  compliance_pass_rate: number | null;
  score_distribution: TeamScoreBandOut;
  agent_comparison: TeamAgentComparisonOut[];
}

// ─── Fetchers ─────────────────────────────────────────────────────────────────

export async function apiGetTeamAnalytics(teamId: string): Promise<TeamAnalyticsOut> {
  return apiFetch<TeamAnalyticsOut>(`/api/v1/teams/${teamId}/analytics`);
}
