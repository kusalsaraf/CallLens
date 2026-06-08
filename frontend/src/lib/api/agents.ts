"use client";

import { apiFetch } from "./client";

// ─── Agent types ──────────────────────────────────────────────────────────────

export interface AgentStatsOut {
  id: string;
  name: string;
  team_id: string;
  created_at: string;
  calls_scored: number;
  avg_overall_score: number;
}

export interface AgentListOut {
  items: AgentStatsOut[];
}

// ─── Coaching note types ──────────────────────────────────────────────────────

export interface CoachingNoteOut {
  id: string;
  agent_id: string;
  call_id: string | null;
  source: "manual" | "auto";
  note: string;
  created_at: string;
}

export interface CoachingListOut {
  items: CoachingNoteOut[];
  agent_id: string | null;
}

export interface CoachingNoteCreate {
  agent_id: string;
  call_id?: string;
  note: string;
}

// ─── Performance types ────────────────────────────────────────────────────────

export interface TrendPointOut {
  date: string;
  avg_overall_score: number;
}

export interface DimensionBreakdownOut {
  dimension_key: string;
  dimension_name: string;
  avg_score: number;
}

export interface VsTeamOut {
  agent_avg: number;
  team_avg: number;
}

export interface AgentPerformanceOut {
  calls_scored: number;
  avg_overall_score: number;
  trend: TrendPointOut[];
  dimension_breakdown: DimensionBreakdownOut[];
  vs_team: VsTeamOut;
}

// ─── Fetchers ─────────────────────────────────────────────────────────────────

export async function apiGetAgents(): Promise<AgentListOut> {
  return apiFetch<AgentListOut>("/api/v1/agents/");
}

export async function apiGetAgent(id: string): Promise<AgentStatsOut> {
  return apiFetch<AgentStatsOut>(`/api/v1/agents/${id}`);
}

export async function apiGetAgentPerformance(
  id: string,
): Promise<AgentPerformanceOut> {
  return apiFetch<AgentPerformanceOut>(`/api/v1/agents/${id}/performance`);
}

export async function apiGetAgentCoaching(id: string): Promise<CoachingListOut> {
  return apiFetch<CoachingListOut>(`/api/v1/agents/${id}/coaching`);
}

export async function apiCreateCoachingNote(
  body: CoachingNoteCreate,
): Promise<CoachingNoteOut> {
  return apiFetch<CoachingNoteOut>("/api/v1/coaching-notes/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function apiDeleteCoachingNote(noteId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/coaching-notes/${noteId}`, {
    method: "DELETE",
  });
}
