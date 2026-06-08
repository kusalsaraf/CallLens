// Score band thresholds — the API band field is authoritative (Phase 4B+).
// apiBandToScoreBand() maps API band strings to our three-way visual system.
// scoreBand() is kept ONLY as a fallback when no API band is present.
export type ScoreBand = "quality" | "at-risk" | "fail";

/**
 * Classify a 0-100 score into the canonical quality band.
 * Mirror of backend core/scoring.py — keep in sync; the API band is authoritative.
 *   quality  >= 80
 *   at-risk  60 – 79
 *   fail     < 60
 */
export function scoreBand(score: number): ScoreBand {
  if (score >= 80) return "quality";
  if (score >= 60) return "at-risk";
  return "fail";
}

export const BAND_LABEL: Record<ScoreBand, string> = {
  quality: "Good",
  "at-risk": "At Risk",
  fail: "Poor",
};

// Tailwind class maps — defined here so Tailwind JIT never purges them.
// Using CSS-var form for at-risk and fail because "text-at-risk" needs the
// hyphen escape that some Tailwind versions handle inconsistently.
export const BAND_TEXT_CLASS: Record<ScoreBand, string> = {
  quality: "text-quality",
  "at-risk": "text-[hsl(var(--at-risk))]",
  fail: "text-[hsl(var(--fail))]",
};

export const BAND_BG_CLASS: Record<ScoreBand, string> = {
  quality: "bg-quality/10",
  "at-risk": "bg-[hsl(var(--at-risk)/0.08)]",
  fail: "bg-[hsl(var(--fail)/0.08)]",
};

export const BAND_RING_CLASS: Record<ScoreBand, string> = {
  quality: "ring-quality/30",
  "at-risk": "ring-[hsl(var(--at-risk)/0.3)]",
  fail: "ring-[hsl(var(--fail)/0.3)]",
};

export const BAND_BORDER_CLASS: Record<ScoreBand, string> = {
  quality: "border-quality/30",
  "at-risk": "border-[hsl(var(--at-risk)/0.3)]",
  fail: "border-[hsl(var(--fail)/0.3)]",
};

// ── API band → frontend ScoreBand ────────────────────────────────────────────
// Canonical API band values (from backend core/scoring.py): "quality" | "at-risk" | "fail"
// Prefer the API band when available; fall back to scoreBand(score).
export function apiBandToScoreBand(
  apiBand: string | undefined,
  scoreFallback: number,
): ScoreBand {
  // Canonical values — pass straight through
  if (apiBand === "quality") return "quality";
  if (apiBand === "at-risk") return "at-risk";
  if (apiBand === "fail") return "fail";
  return scoreBand(scoreFallback);
}

export const API_BAND_LABEL: Record<string, string> = {
  quality: "Good",
  "at-risk": "At Risk",
  fail: "Poor",
};
