"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  apiListCalls,
  type CallOut,
  type CallStatus,
} from "@/lib/api/calls";
import { StatusBadge } from "@/components/calls/StatusBadge";
import { Button } from "@/components/ui/button";
import { cn, formatDuration, formatRelative } from "@/lib/utils";

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "uploaded", label: "Uploaded" },
  { value: "transcribing", label: "Transcribing" },
  { value: "diarizing", label: "Diarizing" },
  { value: "transcribed", label: "Transcribed" },
  { value: "failed", label: "Failed" },
];

export default function CallsPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["calls", { status: statusFilter, page }],
    queryFn: () =>
      apiListCalls({
        status: statusFilter || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="flex flex-col gap-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-foreground">
          Calls
        </h1>
        <Button onClick={() => router.push("/app/upload")}>
          + Upload recording
        </Button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {data && (
          <span className="text-sm text-muted-foreground">
            {data.total} call{data.total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="flex flex-col gap-2">
          {[...Array<null>(5)].map((_, i) => (
            <div
              key={i}
              className="h-14 animate-pulse rounded-lg bg-muted"
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && data?.items.length === 0 && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/50">
            <span className="font-display text-3xl text-muted-foreground/50">
              ◎
            </span>
          </div>
          <div>
            <p className="font-medium text-foreground">No calls yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Upload your first recording to get started.
            </p>
          </div>
          <Button onClick={() => router.push("/app/upload")}>
            Upload recording
          </Button>
        </div>
      )}

      {/* Table */}
      {!isLoading && data && data.items.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                  File
                </th>
                <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                  Status
                </th>
                <th className="px-4 py-3 text-right font-semibold text-muted-foreground tabular">
                  Duration
                </th>
                <th className="px-4 py-3 text-right font-semibold text-muted-foreground">
                  Uploaded
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((call: CallOut, idx) => (
                <tr
                  key={call.id}
                  className={cn(
                    "transition-colors hover:bg-muted/30",
                    idx < data.items.length - 1 && "border-b border-border",
                  )}
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/app/calls/${call.id}`}
                      className="font-medium text-foreground hover:text-primary hover:underline"
                    >
                      {call.original_filename}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={call.status as CallStatus} />
                  </td>
                  <td className="px-4 py-3 text-right tabular text-muted-foreground">
                    {formatDuration(call.duration_seconds)}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {formatRelative(call.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            ← Previous
          </Button>
          <span className="text-sm text-muted-foreground tabular">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </Button>
        </div>
      )}
    </div>
  );
}
