"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  apiActivateRubric,
  apiCloneRubric,
  apiDeleteRubric,
  apiListRubrics,
  type RubricOut,
} from "@/lib/api/rubrics";
import { ApiError } from "@/lib/api/client";
import { cn, formatRelative } from "@/lib/utils";

// ─── Confirm dialog ──────────────────────────────────────────────────────────

function ConfirmDialog({
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-lg">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" className="h-8 text-xs" onClick={onCancel}>
            Cancel
          </Button>
          <Button className="h-8 text-xs" data-testid="confirm-action" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Rubric row ──────────────────────────────────────────────────────────────

function RubricRow({
  rubric,
  onActivate,
  onClone,
  onDelete,
}: {
  rubric: RubricOut;
  onActivate: (id: string) => void;
  onClone: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div
      data-testid="rubric-row"
      className={cn(
        "flex items-center justify-between rounded-lg border bg-card px-4 py-3 transition-shadow hover:shadow-sm",
        rubric.is_active ? "border-[hsl(var(--quality)/0.4)]" : "border-border",
      )}
    >
      <div className="flex items-center gap-3">
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <Link
              href={`/app/rubrics/${rubric.id}/edit`}
              className="text-sm font-medium text-foreground hover:underline"
            >
              {rubric.name}
            </Link>
            {rubric.is_active && (
              <span
                data-testid="active-badge"
                className="rounded-full bg-[hsl(var(--quality)/0.12)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[hsl(var(--quality))]"
              >
                Active
              </span>
            )}
            {rubric.is_default && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                Default
              </span>
            )}
          </div>
          {rubric.description && (
            <p className="text-xs text-muted-foreground">{rubric.description}</p>
          )}
          <p className="text-xs text-muted-foreground">{formatRelative(rubric.created_at)}</p>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <Link href={`/app/rubrics/${rubric.id}/edit`}>
          <Button variant="outline" className="h-7 px-2.5 text-xs" data-testid="edit-btn">
            Edit
          </Button>
        </Link>
        <Button
          variant="outline"
          className="h-7 px-2.5 text-xs"
          data-testid="clone-btn"
          onClick={() => onClone(rubric.id)}
        >
          Clone
        </Button>
        {!rubric.is_active && (
          <Button
            variant="outline"
            className="h-7 px-2.5 text-xs"
            data-testid="activate-btn"
            onClick={() => onActivate(rubric.id)}
          >
            Activate
          </Button>
        )}
        {!rubric.is_active && (
          <Button
            variant="outline"
            className="h-7 px-2.5 text-xs text-destructive hover:bg-destructive/10"
            data-testid="delete-btn"
            onClick={() => onDelete(rubric.id)}
          >
            Delete
          </Button>
        )}
      </div>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function RubricsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["rubrics"],
    queryFn: apiListRubrics,
  });

  const [confirmState, setConfirmState] = useState<{
    type: "activate" | "delete";
    id: string;
  } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const activateMut = useMutation({
    mutationFn: apiActivateRubric,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rubrics"] });
      setConfirmState(null);
    },
  });

  const cloneMut = useMutation({
    mutationFn: apiCloneRubric,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["rubrics"] }),
  });

  const deleteMut = useMutation({
    mutationFn: apiDeleteRubric,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rubrics"] });
      setConfirmState(null);
      setDeleteError(null);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        const detail = (err.body.detail as string) ?? "Cannot delete this rubric.";
        setDeleteError(detail);
      } else {
        setDeleteError("Failed to delete rubric. Please try again.");
      }
    },
  });

  const handleConfirmAction = useCallback(() => {
    if (!confirmState) return;
    if (confirmState.type === "activate") {
      activateMut.mutate(confirmState.id);
    } else {
      setDeleteError(null);
      deleteMut.mutate(confirmState.id);
    }
  }, [confirmState, activateMut, deleteMut]);

  const rubrics = data?.items ?? [];

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-bold text-foreground">Rubrics</h1>
          <p className="text-sm text-muted-foreground">
            Manage scoring rubrics — the active rubric is used for new uploads.
          </p>
        </div>
        <Link href="/app/rubrics/new">
          <Button data-testid="new-rubric-btn">New rubric</Button>
        </Link>
      </div>

      {isLoading && (
        <div data-testid="rubrics-loading" className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg border border-border bg-muted/40" />
          ))}
        </div>
      )}

      {isError && (
        <div data-testid="rubrics-error" className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Failed to load rubrics. Please try again.
        </div>
      )}

      {!isLoading && !isError && rubrics.length === 0 && (
        <div data-testid="rubrics-empty" className="rounded-lg border border-border bg-card p-8 text-center">
          <p className="text-sm text-muted-foreground">
            No rubrics yet. Create your first rubric to get started.
          </p>
        </div>
      )}

      {!isLoading && !isError && rubrics.length > 0 && (
        <div data-testid="rubrics-list" className="flex flex-col gap-2">
          {rubrics.map((r) => (
            <RubricRow
              key={r.id}
              rubric={r}
              onActivate={(id) => setConfirmState({ type: "activate", id })}
              onClone={(id) => cloneMut.mutate(id)}
              onDelete={(id) => {
                setDeleteError(null);
                setConfirmState({ type: "delete", id });
              }}
            />
          ))}
        </div>
      )}

      {/* Delete error inline message */}
      {deleteError && (
        <div
          data-testid="delete-error"
          className="rounded-lg border border-[hsl(var(--fail)/0.3)] bg-[hsl(var(--fail)/0.06)] p-3 text-sm text-[hsl(var(--fail))]"
        >
          {deleteError}
        </div>
      )}

      {/* Confirm dialog */}
      {confirmState && !deleteError && (
        <ConfirmDialog
          title={confirmState.type === "activate" ? "Activate rubric?" : "Delete rubric?"}
          message={
            confirmState.type === "activate"
              ? "Make this the active rubric? New uploads will be scored against it."
              : "Are you sure you want to delete this rubric? This cannot be undone."
          }
          confirmLabel={confirmState.type === "activate" ? "Activate" : "Delete"}
          onConfirm={handleConfirmAction}
          onCancel={() => setConfirmState(null)}
        />
      )}
    </div>
  );
}
