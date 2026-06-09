"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiSearch, type SearchHit, type SegmentSnippet } from "@/lib/api/search";
import { apiListTeams, type AnalyticsFilters } from "@/lib/api/analytics";
import { FilterBar } from "@/components/overview/FilterBar";
import {
  apiBandToScoreBand,
  BAND_TEXT_CLASS,
  BAND_BG_CLASS,
  BAND_BORDER_CLASS,
  BAND_LABEL,
  type ScoreBand,
} from "@/lib/constants/scoreBands";
import { formatRelative, cn } from "@/lib/utils";

const EXAMPLE_QUERIES = [
  "customer threatened to cancel",
  "agent forgot to verify identity",
  "refund request escalated",
  "caller expressed frustration about billing",
];

function formatMs(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function highlightTerms(text: string, query: string): React.ReactNode[] {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length >= 2);
  if (terms.length === 0) return [text];

  const pattern = new RegExp(`(${terms.map(escapeRegex).join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    terms.some((t) => part.toLowerCase() === t) ? (
      <mark key={i} className="rounded bg-primary/20 px-0.5 text-foreground">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function SnippetRow({
  snippet,
  callId,
  query,
}: {
  snippet: SegmentSnippet;
  callId: string;
  query: string;
}) {
  const simPct = Math.round(snippet.similarity * 100);

  return (
    <Link
      href={`/app/calls/${callId}?segment=${snippet.segment_id}`}
      data-testid="snippet-link"
      className="group flex items-start gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted/60"
    >
      <span className="mt-0.5 shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
        {formatMs(snippet.start_ms)}
      </span>
      <span className="min-w-0 flex-1 leading-relaxed text-foreground/90">
        {highlightTerms(snippet.text, query)}
      </span>
      <span
        data-testid="similarity-badge"
        className="mt-0.5 shrink-0 rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] tabular-nums text-muted-foreground"
      >
        {simPct}%
      </span>
    </Link>
  );
}

function ResultCard({ hit, query }: { hit: SearchHit; query: string }) {
  const band: ScoreBand | null =
    hit.overall_score != null
      ? apiBandToScoreBand(hit.band ?? undefined, hit.overall_score)
      : null;

  return (
    <div
      data-testid="search-result-card"
      className={cn(
        "rounded-lg border bg-card transition-shadow hover:shadow-md",
        band ? BAND_BORDER_CLASS[band] : "border-border",
      )}
    >
      <Link
        href={`/app/calls/${hit.call_id}`}
        data-testid="call-link"
        className="flex items-center justify-between gap-4 px-4 py-3"
      >
        <div className="flex items-center gap-3 text-sm">
          <span className="font-medium text-foreground">
            {hit.agent_name ?? "Unknown agent"}
          </span>
          {hit.uploaded_at && (
            <span className="text-muted-foreground">
              {formatRelative(hit.uploaded_at)}
            </span>
          )}
        </div>
        {band && hit.overall_score != null && (
          <span
            data-testid="score-badge"
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums",
              BAND_TEXT_CLASS[band],
              BAND_BG_CLASS[band],
            )}
          >
            {hit.overall_score} · {BAND_LABEL[band]}
          </span>
        )}
      </Link>

      <div className="border-t border-border/50 px-1 py-1">
        {hit.snippets.map((s) => (
          <SnippetRow
            key={s.segment_id}
            snippet={s}
            callId={hit.call_id}
            query={query}
          />
        ))}
      </div>
    </div>
  );
}

export default function SearchPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const urlQ = searchParams.get("q") ?? "";
  const [inputValue, setInputValue] = useState(urlQ);

  const [filters, setFilters] = useState<AnalyticsFilters>({});

  useEffect(() => {
    setInputValue(urlQ);
  }, [urlQ]);

  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: apiListTeams,
    staleTime: 60_000,
  });

  const {
    data: searchData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["search", urlQ, filters],
    queryFn: () =>
      apiSearch({
        q: urlQ,
        limit: 40,
        agent_id: filters.agent_id,
        team_id: filters.team_id,
        date_from: filters.date_from,
        date_to: filters.date_to,
      }),
    enabled: urlQ.trim().length > 0,
  });

  const submitSearch = useCallback(
    (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) return;
      const params = new URLSearchParams(searchParams.toString());
      params.set("q", trimmed);
      router.push(`/app/search?${params.toString()}`);
    },
    [router, searchParams],
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      submitSearch(inputValue);
    }
  }

  function handleExampleClick(q: string) {
    setInputValue(q);
    submitSearch(q);
  }

  const showInitial = !urlQ.trim();
  const showNoResults =
    !showInitial && !isLoading && !isError && searchData?.results.length === 0;
  const showResults =
    !showInitial &&
    !isLoading &&
    !isError &&
    searchData &&
    searchData.results.length > 0;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-xl font-bold text-foreground">
          Search calls
        </h1>
        <p className="text-sm text-muted-foreground">
          Ask anything about your calls — e.g. &ldquo;customer threatened to cancel&rdquo;
          or &ldquo;agent forgot to verify identity&rdquo;
        </p>
      </div>

      {/* Search input */}
      <div className="flex gap-2">
        <input
          data-testid="search-input"
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search across all call transcripts…"
          className="flex-1 rounded-lg border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          data-testid="search-submit"
          onClick={() => submitSearch(inputValue)}
          className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Search
        </button>
      </div>

      {/* Filters */}
      <FilterBar
        filters={filters}
        teams={teams ?? null}
        onFiltersChange={setFilters}
      />

      {/* Initial empty state */}
      {showInitial && (
        <div
          data-testid="search-empty-state"
          className="flex flex-col items-center gap-6 py-12 text-center"
        >
          <div className="text-4xl">⌕</div>
          <p className="text-sm text-muted-foreground">
            Try one of these example queries:
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                data-testid="example-query"
                onClick={() => handleExampleClick(q)}
                className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                &ldquo;{q}&rdquo;
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading skeletons */}
      {isLoading && (
        <div data-testid="search-loading" className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-lg border border-border bg-muted/40"
            />
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div
          data-testid="search-error"
          className="rounded-lg border border-[hsl(var(--fail)/0.3)] bg-[hsl(var(--fail)/0.06)] p-4 text-center text-sm text-[hsl(var(--fail))]"
        >
          Something went wrong — please try again.
        </div>
      )}

      {/* No results */}
      {showNoResults && (
        <div
          data-testid="search-no-results"
          className="flex flex-col items-center gap-3 py-12 text-center"
        >
          <p className="text-sm text-muted-foreground">
            No calls matched — try different wording.
          </p>
        </div>
      )}

      {/* Results */}
      {showResults && (
        <div data-testid="search-results" className="flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">
            {searchData.total} call{searchData.total !== 1 ? "s" : ""} matched
          </p>
          {searchData.results.map((hit) => (
            <ResultCard key={hit.call_id} hit={hit} query={urlQ} />
          ))}
        </div>
      )}
    </div>
  );
}
