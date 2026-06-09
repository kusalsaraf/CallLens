"use client";

import { useCallback, useMemo } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DIMENSION_KINDS,
  KIND_HINTS,
  KIND_LABELS,
  type DimensionKind,
  type DimensionOut,
  type RubricDetailOut,
} from "@/lib/api/rubrics";

// ─── Zod schema mirroring backend validation ─────────────────────────────────

const dimensionSchema = z
  .object({
    key: z.string().min(1, "Key is required").max(64),
    name: z.string().min(1, "Name is required").max(255),
    weight: z.coerce.number().gt(0, "Weight must be positive"),
    kind: z.enum(DIMENSION_KINDS),
    config_phrases: z.array(z.string()).optional(),
    config_checklist: z.array(z.string()).optional(),
    config_guidance: z.string().optional(),
  })
  .superRefine((dim, ctx) => {
    if (dim.kind === "compliance") {
      const phrases = (dim.config_phrases ?? []).filter((p) => p.trim());
      if (phrases.length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "At least one required phrase is needed",
          path: ["config_phrases"],
        });
      }
    }
    if (dim.kind === "script_adherence") {
      const items = (dim.config_checklist ?? []).filter((c) => c.trim());
      if (items.length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "At least one checklist item is needed",
          path: ["config_checklist"],
        });
      }
    }
    if (dim.kind === "custom") {
      if (!dim.config_guidance?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Guidance is required for custom dimensions",
          path: ["config_guidance"],
        });
      }
    }
  });

const rubricSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  description: z.string().optional(),
  dimensions: z.array(dimensionSchema).min(1, "At least one dimension is required"),
});

export type RubricFormData = z.infer<typeof rubricSchema>;
type DimensionFormData = z.infer<typeof dimensionSchema>;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function dimFromApi(d: DimensionOut): DimensionFormData {
  const cfg = d.config ?? {};
  return {
    key: d.key,
    name: d.name,
    weight: d.weight,
    kind: d.kind as DimensionKind,
    config_phrases: (cfg.required_phrases as string[] | undefined) ?? [],
    config_checklist: (cfg.checklist as string[] | undefined) ?? [],
    config_guidance: (cfg.guidance as string | undefined) ?? "",
  };
}

function toApiConfig(dim: DimensionFormData): Record<string, unknown> | null {
  if (dim.kind === "compliance") {
    return { required_phrases: (dim.config_phrases ?? []).filter((p) => p.trim()) };
  }
  if (dim.kind === "script_adherence") {
    return { checklist: (dim.config_checklist ?? []).filter((c) => c.trim()) };
  }
  if (dim.kind === "custom") {
    return { guidance: dim.config_guidance ?? "" };
  }
  return null;
}

export function formToApiPayload(data: RubricFormData) {
  return {
    name: data.name,
    description: data.description || null,
    dimensions: data.dimensions.map((d) => ({
      key: d.key,
      name: d.name,
      weight: d.weight,
      kind: d.kind,
      config: toApiConfig(d),
    })),
  };
}

const EMPTY_DIM: DimensionFormData = {
  key: "",
  name: "",
  weight: 1,
  kind: "sentiment_empathy",
  config_phrases: [],
  config_checklist: [],
  config_guidance: "",
};

// ─── Sub-components ──────────────────────────────────────────────────────────

function PhraseInput({
  value,
  onChange,
  error,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  error?: string;
}) {
  const addPhrase = useCallback(() => {
    const input = document.getElementById("new-phrase") as HTMLInputElement | null;
    if (!input) return;
    const v = input.value.trim();
    if (v && !value.includes(v)) {
      onChange([...value, v]);
      input.value = "";
    }
  }, [value, onChange]);

  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs text-muted-foreground">Required Phrases</Label>
      <div className="flex flex-wrap gap-1.5">
        {value.map((phrase, i) => (
          <span
            key={i}
            data-testid="phrase-chip"
            className="flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs text-foreground"
          >
            {phrase}
            <button
              type="button"
              onClick={() => onChange(value.filter((_, j) => j !== i))}
              className="ml-0.5 text-muted-foreground hover:text-destructive"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-1.5">
        <Input
          id="new-phrase"
          placeholder="Add a required phrase…"
          className="h-7 text-xs"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addPhrase();
            }
          }}
        />
        <Button type="button" variant="outline" className="h-7 px-2 text-xs" onClick={addPhrase}>
          Add
        </Button>
      </div>
      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function ChecklistInput({
  value,
  onChange,
  error,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  error?: string;
}) {
  const addItem = useCallback(() => {
    const input = document.getElementById("new-checklist-item") as HTMLInputElement | null;
    if (!input) return;
    const v = input.value.trim();
    if (v) {
      onChange([...value, v]);
      input.value = "";
    }
  }, [value, onChange]);

  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs text-muted-foreground">Checklist Items</Label>
      <div className="flex flex-col gap-1">
        {value.map((item, i) => (
          <div key={i} data-testid="checklist-item" className="flex items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">{i + 1}.</span>
            <span className="flex-1">{item}</span>
            <button
              type="button"
              onClick={() => onChange(value.filter((_, j) => j !== i))}
              className="text-muted-foreground hover:text-destructive"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <div className="flex gap-1.5">
        <Input
          id="new-checklist-item"
          placeholder="Add a checklist step…"
          className="h-7 text-xs"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addItem();
            }
          }}
        />
        <Button type="button" variant="outline" className="h-7 px-2 text-xs" onClick={addItem}>
          Add
        </Button>
      </div>
      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

// ─── Main builder component ──────────────────────────────────────────────────

interface RubricBuilderProps {
  rubric?: RubricDetailOut;
  onSubmit: (data: RubricFormData) => Promise<void>;
  submitLabel?: string;
  serverError?: string | null;
}

export function RubricBuilder({
  rubric,
  onSubmit,
  submitLabel = "Save rubric",
  serverError,
}: RubricBuilderProps) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<RubricFormData>({
    resolver: zodResolver(rubricSchema),
    mode: "onChange",
    defaultValues: rubric
      ? {
          name: rubric.name,
          description: rubric.description ?? "",
          dimensions: rubric.dimensions.map(dimFromApi),
        }
      : {
          name: "",
          description: "",
          dimensions: [{ ...EMPTY_DIM }],
        },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "dimensions" });

  const watchedDims = watch("dimensions");

  const totalWeight = useMemo(
    () => watchedDims.reduce((s, d) => s + (Number(d.weight) || 0), 0),
    [watchedDims],
  );

  return (
    <form
      data-testid="rubric-form"
      onSubmit={handleSubmit(onSubmit)}
      noValidate
      className="flex flex-col gap-6"
    >
      {/* ── Name / Description ─────────────────────────────────────────── */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="name">Rubric Name</Label>
          <Input
            id="name"
            placeholder="e.g. Support QA v2"
            aria-invalid={!!errors.name}
            {...register("name")}
          />
          {errors.name && (
            <p className="text-xs text-destructive" role="alert">
              {errors.name.message}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="description">Description</Label>
          <Input
            id="description"
            placeholder="Optional description"
            {...register("description")}
          />
        </div>
      </div>

      {/* ── Dimensions ─────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">Dimensions</h3>
          <Button
            type="button"
            variant="outline"
            className="h-7 px-3 text-xs"
            data-testid="add-dimension"
            onClick={() => append({ ...EMPTY_DIM })}
          >
            + Add dimension
          </Button>
        </div>

        {errors.dimensions?.root && (
          <p className="text-xs text-destructive" role="alert">
            {errors.dimensions.root.message}
          </p>
        )}

        {fields.map((field, idx) => {
          const dimErrors = errors.dimensions?.[idx];
          const dim = watchedDims[idx];
          const kind = dim?.kind;
          const weight = Number(dim?.weight) || 0;
          const pct = totalWeight > 0 ? ((weight / totalWeight) * 100).toFixed(1) : "0.0";

          return (
            <div
              key={field.id}
              data-testid="dimension-row"
              className="rounded-lg border border-border bg-card p-4"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  Dimension {idx + 1}
                </span>
                {fields.length > 1 && (
                  <button
                    type="button"
                    data-testid="remove-dimension"
                    onClick={() => remove(idx)}
                    className="text-xs text-muted-foreground hover:text-destructive"
                  >
                    Remove
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* Name */}
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Name</Label>
                  <Input
                    placeholder="Dimension name"
                    className="h-8 text-sm"
                    aria-invalid={!!dimErrors?.name}
                    {...register(`dimensions.${idx}.name`)}
                    data-testid="dim-name"
                  />
                  {dimErrors?.name && (
                    <p className="text-xs text-destructive">{dimErrors.name.message}</p>
                  )}
                </div>

                {/* Key */}
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Key</Label>
                  <Input
                    placeholder="e.g. empathy"
                    className="h-8 text-sm"
                    aria-invalid={!!dimErrors?.key}
                    {...register(`dimensions.${idx}.key`)}
                  />
                  {dimErrors?.key && (
                    <p className="text-xs text-destructive">{dimErrors.key.message}</p>
                  )}
                </div>

                {/* Kind */}
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Kind</Label>
                  <select
                    className="h-8 rounded-md border border-border bg-background px-2 text-sm"
                    data-testid="dim-kind"
                    {...register(`dimensions.${idx}.kind`)}
                  >
                    {DIMENSION_KINDS.map((k) => (
                      <option key={k} value={k}>
                        {KIND_LABELS[k]}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Weight + normalized % */}
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Weight</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      step="0.01"
                      min="0.01"
                      className="h-8 text-sm"
                      aria-invalid={!!dimErrors?.weight}
                      data-testid="dim-weight"
                      {...register(`dimensions.${idx}.weight`, { valueAsNumber: true })}
                    />
                    <span
                      data-testid="weight-pct"
                      className="whitespace-nowrap font-mono text-xs tabular-nums text-muted-foreground"
                    >
                      {pct}%
                    </span>
                  </div>
                  {dimErrors?.weight && (
                    <p className="text-xs text-destructive">{dimErrors.weight.message}</p>
                  )}
                </div>
              </div>

              {/* Kind hint or config inputs */}
              <div className="mt-3">
                {kind === "compliance" && (
                  <PhraseInput
                    value={dim?.config_phrases ?? []}
                    onChange={(v) => setValue(`dimensions.${idx}.config_phrases`, v, { shouldValidate: true })}
                    error={dimErrors?.config_phrases?.message as string | undefined}
                  />
                )}
                {kind === "script_adherence" && (
                  <ChecklistInput
                    value={dim?.config_checklist ?? []}
                    onChange={(v) => setValue(`dimensions.${idx}.config_checklist`, v, { shouldValidate: true })}
                    error={dimErrors?.config_checklist?.message as string | undefined}
                  />
                )}
                {kind === "custom" && (
                  <div className="flex flex-col gap-1.5">
                    <Label className="text-xs text-muted-foreground">
                      Scoring Guidance
                    </Label>
                    <textarea
                      rows={3}
                      placeholder="Describe what this criterion evaluates…"
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      data-testid="dim-guidance"
                      {...register(`dimensions.${idx}.config_guidance`)}
                    />
                    {dimErrors?.config_guidance && (
                      <p className="text-xs text-destructive" role="alert">
                        {dimErrors.config_guidance.message as string}
                      </p>
                    )}
                  </div>
                )}
                {kind &&
                  !["compliance", "script_adherence", "custom"].includes(kind) && (
                    <p className="text-xs italic text-muted-foreground">
                      {KIND_HINTS[kind as DimensionKind]}
                    </p>
                  )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Note about active rubric */}
      <p className="text-xs text-muted-foreground">
        Editing the active rubric affects <strong>future</strong> scoring only.
        Already-scored calls keep their results until reprocessed.
      </p>

      {serverError && (
        <p className="text-sm text-destructive" role="alert">
          {serverError}
        </p>
      )}

      <div className="flex gap-3">
        <Button type="submit" disabled={isSubmitting} data-testid="rubric-submit">
          {isSubmitting ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
