// Score band thresholds — the API may return the band directly in a later phase;
// this is the interim single source of truth for client-side band classification.
export type ScoreBand = "quality" | "at-risk" | "fail";

/** Return the quality band for a 0–100 score. */
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
