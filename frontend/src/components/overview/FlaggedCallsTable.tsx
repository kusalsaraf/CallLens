"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { BAND_TEXT_CLASS, apiBandToScoreBand } from "@/lib/constants/scoreBands";
import type { FlaggedListOut } from "@/lib/api/analytics";

interface FlaggedCallsTableProps {
  data: FlaggedListOut;
  onShowMore: () => void;
}

function fmtScore(s: number): string {
  return s.toFixed(0);
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Compact paginated table of at-risk / escalated calls linking to /app/calls/[id]. */
export function FlaggedCallsTable({ data, onShowMore }: FlaggedCallsTableProps) {
  if (data.total === 0) {
    return (
      <div
        data-testid="flagged-empty"
        className="rounded-lg border border-border bg-card p-5 text-center text-sm text-muted-foreground"
      >
        No flagged calls in this range — nice.
      </div>
    );
  }

  const hasMore = data.offset + data.items.length < data.total;

  return (
    <div
      data-testid="flagged-table"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          Flagged / At-Risk Calls
        </h3>
        <span className="text-xs text-muted-foreground tabular">{data.total} total</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="flagged-calls-list">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium text-muted-foreground">
              <th className="pb-2 pr-4">Agent</th>
              <th className="pb-2 pr-4">Score</th>
              <th className="pb-2 pr-4">Band</th>
              <th className="pb-2 pr-4">Uploaded</th>
              <th className="pb-2">Reason</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => {
              const scoreBand = apiBandToScoreBand(row.band as never, row.overall_score);
              const textClass = BAND_TEXT_CLASS[scoreBand];
              return (
                <tr
                  key={row.call_id}
                  data-testid={`flagged-row-${row.call_id}`}
                  className="border-b border-border/50 hover:bg-muted/40 transition-colors"
                >
                  <td className="py-2 pr-4 font-medium">
                    <Link
                      href={`/app/calls/${row.call_id}`}
                      className="hover:underline text-foreground"
                    >
                      {row.agent_name ?? "Unknown"}
                    </Link>
                  </td>
                  <td className={cn("py-2 pr-4 tabular font-semibold", textClass)}>
                    {fmtScore(row.overall_score)}
                  </td>
                  <td className={cn("py-2 pr-4 capitalize", textClass)}>{row.band}</td>
                  <td className="py-2 pr-4 tabular text-muted-foreground">
                    {fmtDate(row.uploaded_at)}
                  </td>
                  <td className="py-2 text-muted-foreground text-xs">
                    {row.escalation_reason ?? (row.escalate_for_review ? "Escalated" : "—")}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {hasMore && (
        <button
          data-testid="flagged-show-more"
          onClick={onShowMore}
          className="self-start text-xs text-primary underline-offset-2 hover:underline"
        >
          Show more ({data.total - (data.offset + data.items.length)} remaining)
        </button>
      )}
    </div>
  );
}
