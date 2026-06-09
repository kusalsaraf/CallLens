"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  apiActivateRubric,
  apiGetRubric,
  apiUpdateRubric,
} from "@/lib/api/rubrics";
import { ApiError } from "@/lib/api/client";
import {
  RubricBuilder,
  formToApiPayload,
  type RubricFormData,
} from "@/components/rubrics/RubricBuilder";

export default function EditRubricPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  const { data: rubric, isLoading, isError } = useQuery({
    queryKey: ["rubric", id],
    queryFn: () => apiGetRubric(id),
    enabled: !!id,
  });

  const updateMut = useMutation({
    mutationFn: (data: ReturnType<typeof formToApiPayload>) => apiUpdateRubric(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rubrics"] });
      queryClient.invalidateQueries({ queryKey: ["rubric", id] });
      router.push("/app/rubrics");
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422) {
        const detail = err.body.detail;
        setServerError(typeof detail === "string" ? detail : "Validation failed. Check your inputs.");
      } else {
        setServerError("Failed to update rubric. Please try again.");
      }
    },
  });

  const activateMut = useMutation({
    mutationFn: apiActivateRubric,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rubrics"] });
      queryClient.invalidateQueries({ queryKey: ["rubric", id] });
    },
  });

  const handleSubmit = useCallback(
    async (data: RubricFormData) => {
      setServerError(null);
      const payload = formToApiPayload(data);
      updateMut.mutate(payload);
    },
    [updateMut],
  );

  if (isLoading) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="mt-6 flex flex-col gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg border border-border bg-muted/40" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !rubric) {
    return (
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-sm text-muted-foreground">Rubric not found.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-bold text-foreground">Edit rubric</h1>
          <p className="text-sm text-muted-foreground">
            {rubric.is_active ? "This is the active rubric." : "This rubric is inactive."}
          </p>
        </div>
        {!rubric.is_active && (
          <Button
            variant="outline"
            data-testid="activate-from-edit"
            onClick={() => activateMut.mutate(id)}
            disabled={activateMut.isPending}
          >
            {activateMut.isPending ? "Activating…" : "Activate"}
          </Button>
        )}
      </div>
      <RubricBuilder
        key={rubric.id}
        rubric={rubric}
        onSubmit={handleSubmit}
        submitLabel="Save changes"
        serverError={serverError}
      />
    </div>
  );
}
