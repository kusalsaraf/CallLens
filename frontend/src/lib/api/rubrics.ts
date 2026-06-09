"use client";

import { apiFetch } from "./client";

// ─── Dimension kinds (mirrors backend DimensionKind StrEnum) ─────────────────

export const DIMENSION_KINDS = [
  "sentiment_empathy",
  "script_adherence",
  "compliance",
  "objection_handling",
  "talk_listen",
  "outcome",
  "custom",
] as const;

export type DimensionKind = (typeof DIMENSION_KINDS)[number];

export const KIND_LABELS: Record<DimensionKind, string> = {
  sentiment_empathy: "Sentiment & Empathy",
  script_adherence: "Script Adherence",
  compliance: "Compliance",
  objection_handling: "Objection Handling",
  talk_listen: "Talk/Listen Ratio",
  outcome: "Call Outcome",
  custom: "Custom",
};

export const KIND_HINTS: Record<DimensionKind, string> = {
  sentiment_empathy: "Scores the agent's tone, word choice, and empathic responses.",
  script_adherence: "Checks the agent followed the call structure steps.",
  compliance: "Checks the agent said all required phrases.",
  objection_handling: "Scores how well the agent addressed customer objections.",
  talk_listen: "Deterministic score from agent/customer speaking ratio.",
  outcome: "Call outcome — handled by the supervisor.",
  custom: "Custom criteria scored by AI using your guidance.",
};

// ─── Response types ──────────────────────────────────────────────────────────

export interface DimensionOut {
  id: string;
  key: string;
  name: string;
  weight: number;
  kind: string;
  config: Record<string, unknown> | null;
  created_at: string;
}

export interface RubricOut {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
}

export interface RubricDetailOut extends RubricOut {
  dimensions: DimensionOut[];
}

export interface RubricListOut {
  items: RubricOut[];
}

// ─── Input types ─────────────────────────────────────────────────────────────

export interface DimensionIn {
  key: string;
  name: string;
  weight: number;
  kind: DimensionKind;
  config?: Record<string, unknown> | null;
}

export interface RubricCreateIn {
  name: string;
  description?: string | null;
  dimensions: DimensionIn[];
}

export interface RubricUpdateIn {
  name?: string | null;
  description?: string | null;
  dimensions?: DimensionIn[] | null;
}

// ─── Fetchers ────────────────────────────────────────────────────────────────

export async function apiListRubrics(): Promise<RubricListOut> {
  return apiFetch<RubricListOut>("/api/v1/rubrics");
}

export async function apiGetRubric(id: string): Promise<RubricDetailOut> {
  return apiFetch<RubricDetailOut>(`/api/v1/rubrics/${id}`);
}

export async function apiCreateRubric(data: RubricCreateIn): Promise<RubricDetailOut> {
  return apiFetch<RubricDetailOut>("/api/v1/rubrics", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function apiUpdateRubric(
  id: string,
  data: RubricUpdateIn,
): Promise<RubricDetailOut> {
  return apiFetch<RubricDetailOut>(`/api/v1/rubrics/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function apiActivateRubric(id: string): Promise<RubricDetailOut> {
  return apiFetch<RubricDetailOut>(`/api/v1/rubrics/${id}/activate`, {
    method: "POST",
  });
}

export async function apiCloneRubric(id: string): Promise<RubricDetailOut> {
  return apiFetch<RubricDetailOut>(`/api/v1/rubrics/${id}/clone`, {
    method: "POST",
  });
}

export async function apiDeleteRubric(id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/rubrics/${id}`, {
    method: "DELETE",
  });
}
