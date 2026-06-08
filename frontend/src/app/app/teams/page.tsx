"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CardSkeleton } from "@/components/overview/CardSkeleton";
import { apiListTeams } from "@/lib/api/analytics";

/** Teams list — click a card to view team analytics. */
export default function TeamsPage() {
  const { data: teams, isLoading } = useQuery({
    queryKey: ["teams"],
    queryFn: apiListTeams,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-xl font-bold text-foreground">Teams</h1>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <CardSkeleton key={i} height="h-24" data-testid="card-skeleton" />
          ))}
        </div>
      ) : teams && teams.items.length > 0 ? (
        <div
          data-testid="teams-list"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          {teams.items.map((t) => (
            <Link
              key={t.id}
              href={`/app/teams/${t.id}`}
              data-testid={`team-card-${t.id}`}
              className="flex flex-col gap-2 rounded-lg border border-border bg-card p-5 shadow-sm hover:bg-muted/40 transition-colors"
            >
              <span className="font-semibold text-foreground">{t.name}</span>
              <span className="text-xs text-muted-foreground">View analytics →</span>
            </Link>
          ))}
        </div>
      ) : (
        <div
          data-testid="teams-empty"
          className="rounded-lg border border-border bg-card p-10 text-center text-sm text-muted-foreground"
        >
          No teams found.
        </div>
      )}
    </div>
  );
}
