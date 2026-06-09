"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiCreateRubric } from "@/lib/api/rubrics";
import { ApiError } from "@/lib/api/client";
import {
  RubricBuilder,
  formToApiPayload,
  type RubricFormData,
} from "@/components/rubrics/RubricBuilder";

export default function NewRubricPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: apiCreateRubric,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rubrics"] });
      router.push("/app/rubrics");
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422) {
        const detail = err.body.detail;
        setServerError(typeof detail === "string" ? detail : "Validation failed. Check your inputs.");
      } else {
        setServerError("Failed to create rubric. Please try again.");
      }
    },
  });

  const handleSubmit = useCallback(
    async (data: RubricFormData) => {
      setServerError(null);
      const payload = formToApiPayload(data);
      createMut.mutate(payload);
    },
    [createMut],
  );

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="font-display text-xl font-bold text-foreground">New rubric</h1>
        <p className="text-sm text-muted-foreground">
          Create a new scoring rubric. It will be saved as inactive — activate it when ready.
        </p>
      </div>
      <RubricBuilder
        onSubmit={handleSubmit}
        submitLabel="Create rubric"
        serverError={serverError}
      />
    </div>
  );
}
