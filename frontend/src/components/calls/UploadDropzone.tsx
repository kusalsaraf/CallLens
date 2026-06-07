"use client";

import { useCallback, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  ALLOWED_AUDIO_MIMES,
  MAX_UPLOAD_BYTES,
  apiUploadCall,
  type CallOut,
} from "@/lib/api/calls";
import { ApiError } from "@/lib/api/client";

interface UploadDropzoneProps {
  onUploaded: (call: CallOut) => void;
  className?: string;
}

export function UploadDropzone({ onUploaded, className }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const validate = useCallback((file: File): string | null => {
    if (!ALLOWED_AUDIO_MIMES.has(file.type)) {
      return `Unsupported file type "${file.type}". Please upload an audio file (MP3, WAV, OGG, etc.).`;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return `File exceeds the maximum allowed size of 200 MB.`;
    }
    return null;
  }, []);

  const upload = useCallback(
    async (file: File) => {
      const err = validate(file);
      if (err) {
        setError(err);
        return;
      }
      setError(null);
      setProgress(0);
      try {
        const call = await apiUploadCall(file, setProgress);
        setProgress(null);
        onUploaded(call);
      } catch (e) {
        setProgress(null);
        if (e instanceof ApiError) {
          const msg =
            (e.body.message as string | undefined) ??
            "Upload failed. Please try again.";
          setError(msg);
        } else {
          setError("Upload failed. Please try again.");
        }
      }
    },
    [validate, onUploaded],
  );

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    // Reset so the same file can be re-selected after an error
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void upload(file);
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-border bg-muted/30 px-8 py-14 text-center transition-colors",
          isDragOver && "border-primary bg-primary/5",
          progress != null && "pointer-events-none opacity-70",
        )}
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/50">
          <span className="text-3xl text-muted-foreground">♬</span>
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">
            Drag and drop your recording here
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            or{" "}
            <span className="text-primary underline-offset-2 hover:underline">
              choose file
            </span>{" "}
            · MP3, WAV, OGG, FLAC up to 200 MB
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="audio/*"
          className="sr-only"
          onChange={handleFileChange}
        />
      </div>

      {/* Upload progress */}
      {progress != null && (
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Uploading…</span>
            <span className="tabular">{progress}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-150"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Validation / server error */}
      {error && (
        <p role="alert" className="text-sm text-[hsl(var(--fail))]">
          {error}
        </p>
      )}
    </div>
  );
}
