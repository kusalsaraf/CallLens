"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiDeleteCall,
  apiGetCall,
  apiGetTranscript,
  fetchAudioObjectUrl,
  isTerminalStatus,
  type CallOut,
  type CallStatus,
} from "@/lib/api/calls";
import { StatusBadge } from "@/components/calls/StatusBadge";
import { CallStatusStepper } from "@/components/calls/CallStatusStepper";
import { AudioPlayer, type AudioPlayerRef } from "@/components/calls/AudioPlayer";
import { TranscriptPanel } from "@/components/calls/TranscriptPanel";
import { Button } from "@/components/ui/button";
import { formatDuration, formatRelative } from "@/lib/utils";

export default function CallDetailPage() {
  const params = useParams<{ id: string }>();
  const callId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();

  const audioPlayerRef = useRef<AudioPlayerRef>(null);
  const [currentTimeSec, setCurrentTimeSec] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data: call, isLoading } = useQuery<CallOut>({
    queryKey: ["call", callId],
    queryFn: () => apiGetCall(callId),
    enabled: !!callId,
  });

  const terminal = call ? isTerminalStatus(call.status as CallStatus) : false;
  const transcribed = call?.status === "transcribed";

  const { data: transcript } = useQuery({
    queryKey: ["call-transcript", callId],
    queryFn: () => apiGetTranscript(callId),
    enabled: transcribed,
  });

  // Fetch audio blob URL when call is transcribed
  useEffect(() => {
    if (!transcribed || audioUrl) return;
    fetchAudioObjectUrl(callId)
      .then((url) => setAudioUrl(url))
      .catch(console.error);
  }, [transcribed, callId, audioUrl]);

  // Revoke blob URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  // When SSE stepper completes, invalidate and re-fetch the call
  const handleStepperComplete = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["call", callId] });
    await queryClient.invalidateQueries({ queryKey: ["calls"] });
  }, [callId, queryClient]);

  const handleSeek = useCallback((ms: number) => {
    audioPlayerRef.current?.seekTo(ms / 1000);
  }, []);

  async function handleDelete() {
    setIsDeleting(true);
    try {
      await apiDeleteCall(callId);
      router.push("/app/calls");
    } catch {
      setIsDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!call) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <p className="text-muted-foreground">Call not found.</p>
        <Button variant="outline" onClick={() => router.push("/app/calls")}>
          Back to calls
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push("/app/calls")}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              ← Calls
            </button>
          </div>
          <h1 className="font-display text-xl font-bold text-foreground">
            {call.original_filename}
          </h1>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <StatusBadge status={call.status as CallStatus} />
            {call.duration_seconds != null && (
              <span className="tabular">{formatDuration(call.duration_seconds)}</span>
            )}
            <span>{formatRelative(call.created_at)}</span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled>
            Export to CRM
          </Button>

          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Delete this call?</span>
              <Button
                variant="destructive"
                size="sm"
                disabled={isDeleting}
                onClick={handleDelete}
              >
                {isDeleting ? "Deleting…" : "Yes, delete"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmDelete(false)}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmDelete(true)}
            >
              Delete
            </Button>
          )}
        </div>
      </div>

      {/* ── Processing state: live stepper ── */}
      {!terminal && (
        <CallStatusStepper
          callId={callId}
          initialStatus={call.status as CallStatus}
          onComplete={handleStepperComplete}
        />
      )}

      {/* ── Audio player (once transcribed + blob ready) ── */}
      {transcribed && audioUrl && (
        <AudioPlayer
          ref={audioPlayerRef}
          src={audioUrl}
          onTimeUpdate={setCurrentTimeSec}
        />
      )}

      {/* ── Transcript panel ── */}
      {transcribed && (
        <TranscriptPanel
          segments={transcript?.segments ?? []}
          currentTimeSec={currentTimeSec}
          onSeek={handleSeek}
          className="max-h-[60vh]"
        />
      )}

      {/* ── Failed state detail ── */}
      {call.status === "failed" && call.status_detail && (
        <div className="rounded-lg border border-[hsl(var(--fail)/0.3)] bg-[hsl(var(--fail)/0.06)] p-4 text-sm text-[hsl(var(--fail))]">
          <p className="font-semibold">Processing failed</p>
          <p className="mt-1">{call.status_detail}</p>
        </div>
      )}
    </div>
  );
}
