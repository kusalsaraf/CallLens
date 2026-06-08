"use client";

import type { AnalyticsFilters, TeamListOut } from "@/lib/api/analytics";

interface DatePreset {
  label: string;
  days: number | null;
}

const DATE_PRESETS: DatePreset[] = [
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
  { label: "All time", days: null },
];

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoSubtractDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

/** Compute which preset label is currently active given the filter state. */
function activePreset(f: AnalyticsFilters): string | null {
  if (!f.date_from && !f.date_to) return "All time";
  const today = isoToday();
  for (const p of DATE_PRESETS) {
    if (p.days === null) continue;
    const expected = isoSubtractDays(p.days);
    if (f.date_from === expected && (!f.date_to || f.date_to === today)) return p.label;
  }
  return null;
}

interface FilterBarProps {
  filters: AnalyticsFilters;
  teams: TeamListOut | null;
  onFiltersChange: (f: AnalyticsFilters) => void;
}

/** Date-range presets + team selector, drives all dashboard queries. */
export function FilterBar({ filters, teams, onFiltersChange }: FilterBarProps) {
  const current = activePreset(filters);

  function applyPreset(p: DatePreset): void {
    if (p.days === null) {
      onFiltersChange({ ...filters, date_from: undefined, date_to: undefined });
    } else {
      onFiltersChange({
        ...filters,
        date_from: isoSubtractDays(p.days),
        date_to: isoToday(),
      });
    }
  }

  function onTeamChange(e: React.ChangeEvent<HTMLSelectElement>): void {
    const val = e.target.value;
    onFiltersChange({ ...filters, team_id: val || undefined });
  }

  return (
    <div
      data-testid="filter-bar"
      className="flex flex-wrap items-center gap-3"
    >
      {/* Date presets */}
      <div
        data-testid="date-presets"
        className="flex gap-1 rounded-md border border-border p-0.5"
      >
        {DATE_PRESETS.map((p) => (
          <button
            key={p.label}
            data-testid={`preset-${p.label.toLowerCase().replace(/\s+/g, "-")}`}
            onClick={() => applyPreset(p)}
            className={
              current === p.label
                ? "rounded px-3 py-1 text-xs font-medium bg-primary text-primary-foreground"
                : "rounded px-3 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
            }
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Team selector */}
      {teams && teams.items.length > 0 && (
        <select
          data-testid="team-selector"
          value={filters.team_id ?? ""}
          onChange={onTeamChange}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All teams</option>
          {teams.items.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
