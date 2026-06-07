"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import type { CallOut } from "@/lib/api/calls";
import { isTerminalStatus } from "@/lib/api/calls";
import { CallStatusStepper } from "@/components/calls/CallStatusStepper";
import { UploadDropzone } from "@/components/calls/UploadDropzone";

export default function UploadPage() {
  const router = useRouter();
  const [uploadedCall, setUploadedCall] = useState<CallOut | null>(null);

  const handleUploaded = useCallback((call: CallOut) => {
    setUploadedCall(call);
    if (isTerminalStatus(call.status)) {
      router.push(`/app/calls/${call.id}`);
    }
  }, [router]);

  const handleComplete = useCallback(
    (status: string) => {
      if (status === "transcribed" && uploadedCall) {
        router.push(`/app/calls/${uploadedCall.id}`);
      }
    },
    [router, uploadedCall],
  );

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-8 pt-8">
      <div>
        <h1 className="font-display text-2xl font-bold text-foreground">
          Upload recording
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          CallLens will transcribe and analyse the call automatically.
        </p>
      </div>

      {uploadedCall ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Uploaded{" "}
            <span className="font-medium text-foreground">
              {uploadedCall.original_filename}
            </span>
            . Processing now…
          </p>
          <CallStatusStepper
            callId={uploadedCall.id}
            initialStatus={uploadedCall.status}
            onComplete={handleComplete}
          />
        </div>
      ) : (
        <UploadDropzone onUploaded={handleUploaded} />
      )}
    </div>
  );
}
