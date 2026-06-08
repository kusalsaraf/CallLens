"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import {
  apiCreateCoachingNote,
  apiDeleteCoachingNote,
  type CoachingNoteOut,
} from "@/lib/api/agents";

interface CoachingPanelProps {
  agentId: string;
  notes: CoachingNoteOut[];
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Coaching notes panel with composer (manual) and delete (manual-only). */
export function CoachingPanel({ agentId, notes }: CoachingPanelProps) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (note: string) =>
      apiCreateCoachingNote({ agent_id: agentId, note }),
    onSuccess: () => {
      setDraft("");
      void qc.invalidateQueries({ queryKey: ["agent-coaching", agentId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (noteId: string) => apiDeleteCoachingNote(noteId),
    onSuccess: () => {
      setDeleteTarget(null);
      void qc.invalidateQueries({ queryKey: ["agent-coaching", agentId] });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed) return;
    createMutation.mutate(trimmed);
  }

  return (
    <div
      data-testid="coaching-panel"
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      <h3 className="text-sm font-semibold text-foreground">Coaching Notes</h3>

      {/* Note composer */}
      <form
        data-testid="coaching-composer"
        onSubmit={handleSubmit}
        className="flex flex-col gap-2"
      >
        <textarea
          data-testid="coaching-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a coaching note…"
          rows={3}
          className="w-full resize-none rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <div className="flex items-center justify-between">
          {createMutation.isError && (
            <p className="text-xs text-[hsl(346_80%_35%)]">Failed to save note.</p>
          )}
          <button
            data-testid="coaching-submit"
            type="submit"
            disabled={!draft.trim() || createMutation.isPending}
            className="ml-auto rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            {createMutation.isPending ? "Saving…" : "Add Note"}
          </button>
        </div>
      </form>

      {/* Notes list */}
      {notes.length === 0 ? (
        <div
          data-testid="coaching-empty"
          className="text-sm text-muted-foreground"
        >
          No coaching notes yet.
        </div>
      ) : (
        <div className="flex flex-col gap-3" data-testid="coaching-notes-list">
          {notes.map((n) => (
            <div
              key={n.id}
              data-testid={`coaching-note-${n.id}`}
              className={cn(
                "flex flex-col gap-1 rounded-md border p-3 text-sm",
                n.source === "auto"
                  ? "border-border/50 bg-muted/30 text-muted-foreground"
                  : "border-border bg-background text-foreground",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  {n.source === "auto" && (
                    <span
                      data-testid={`note-auto-badge-${n.id}`}
                      className="rounded px-1.5 py-0.5 text-[10px] font-medium bg-muted text-muted-foreground"
                    >
                      AI
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {fmtDate(n.created_at)}
                  </span>
                </div>

                {/* Manual notes only get delete */}
                {n.source === "manual" && (
                  deleteTarget === n.id ? (
                    <div className="flex gap-2">
                      <button
                        data-testid={`note-delete-confirm-${n.id}`}
                        onClick={() => deleteMutation.mutate(n.id)}
                        disabled={deleteMutation.isPending}
                        className="text-xs text-[hsl(346_80%_35%)] hover:underline disabled:opacity-50"
                      >
                        Confirm
                      </button>
                      <button
                        data-testid={`note-delete-cancel-${n.id}`}
                        onClick={() => setDeleteTarget(null)}
                        className="text-xs text-muted-foreground hover:underline"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      data-testid={`note-delete-${n.id}`}
                      onClick={() => setDeleteTarget(n.id)}
                      className="text-xs text-muted-foreground hover:text-[hsl(346_80%_35%)]"
                      aria-label="Delete note"
                    >
                      ✕
                    </button>
                  )
                )}
              </div>
              <p className="leading-relaxed">{n.note}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
