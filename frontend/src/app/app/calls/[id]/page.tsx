"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiDeleteCall,
  apiGetAnalysis,
  apiGetCall,
  apiGetTrace,
  apiGetTranscript,
  fetchAudioObjectUrl,
  isTerminalStatus,
  type CallAnalysisOut,
  type CallOut,
  type CallStatus,
  type TraceOut,
} from "@/lib/api/calls";
import { StatusBadge } from "@/components/calls/StatusBadge";
import { CallStatusStepper } from "@/components/calls/CallStatusStepper";
import { AudioPlayer, type AudioPlayerRef } from "@/components/calls/AudioPlayer";
import { TranscriptPanel } from "@/components/calls/TranscriptPanel";
import { ScorecardPanel } from "@/components/calls/ScorecardPanel";
import { OverallScoreHero } from "@/components/calls/OverallScoreHero";
import { EscalationBanner } from "@/components/calls/EscalationBanner";
import { SummaryActionsCard } from "@/components/calls/SummaryActionsCard";
import { ConversationDynamics } from "@/components/calls/ConversationDynamics";
import { AgentRunTrace } from "@/components/calls/AgentRunTrace";
import { Button } from "@/components/ui/button";
import { formatRelative } from "@/lib/utils";

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
  const [focusedSegmentId, setFocusedSegmentId] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const deepLinkSegment = searchParams.get("segment");

  const { data: call, isLoading } = useQuery<CallOut>({
    queryKey: ["call", callId],
    queryFn: () => apiGetCall(callId),
    enabled: !!callId,
  });

  const terminal = call ? isTerminalStatus(call.status as CallStatus) : false;
  const isScored = call?.status === "scored";
  const hasTranscript =
    call?.status === "transcribed" ||
    call?.status === "scoring" ||
    call?.status === "scored";

  const { data: transcript } = useQuery({
    queryKey: ["call-transcript", callId],
    queryFn: () => apiGetTranscript(callId),
    enabled: hasTranscript,
  });

  const { data: analysis } = useQuery<CallAnalysisOut>({
    queryKey: ["call-analysis", callId],
    queryFn: () => apiGetAnalysis(callId),
    enabled: isScored,
    staleTime: 30_000,
  });

  const { data: trace } = useQuery<TraceOut>({
    queryKey: ["call-trace", callId],
    queryFn: () => apiGetTrace(callId),
    enabled: isScored,
    staleTime: 30_000,
  });

  // Fetch audio blob URL once transcript is available
  useEffect(() => {
    if (!hasTranscript || audioUrl) return;
    fetchAudioObjectUrl(callId)
      .then((url) => setAudioUrl(url))
      .catch(console.error);
  }, [hasTranscript, callId, audioUrl]);

  // Revoke blob URL on unmount
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  // Deep-link: ?segment=<id> → seek audio + flash transcript segment
  useEffect(() => {
    if (!deepLinkSegment || !transcript) return;
    const seg = transcript.segments.find((s) => s.id === deepLinkSegment);
    if (!seg) return;
    audioPlayerRef.current?.seekTo(seg.start_ms / 1000);
    setFocusedSegmentId(seg.id);
  }, [deepLinkSegment, transcript]);

  const handleStepperComplete = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["call", callId] });
    await queryClient.invalidateQueries({ queryKey: ["calls"] });
    await queryClient.invalidateQueries({ queryKey: ["call-scores", callId] });
    await queryClient.invalidateQueries({ queryKey: ["call-analysis", callId] });
    await queryClient.invalidateQueries({ queryKey: ["call-trace", callId] });
  }, [callId, queryClient]);

  const handleSeek = useCallback((ms: number) => {
    audioPlayerRef.current?.seekTo(ms / 1000);
  }, []);

  const handleEvidenceClick = useCallback(
    (segmentId: string, startMs: number) => {
      audioPlayerRef.current?.seekTo(startMs / 1000);
      setFocusedSegmentId(segmentId);
    },
    [],
  );

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

  const segments = transcript?.segments ?? [];

  return (
    <div className="flex flex-col gap-4">
      {/* ── Page header: breadcrumb + filename + meta + actions ── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <button
            onClick={() => router.push("/app/calls")}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Calls
          </button>
          <h1 className="font-display text-xl font-bold text-foreground">
            {call.original_filename}
          </h1>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <StatusBadge status={call.status as CallStatus} />
            <span>{formatRelative(call.created_at)}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled>
            Export to CRM
          </Button>
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Delete this call?
              </span>
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

      {/* ── Failed state ── */}
      {call.status === "failed" && call.status_detail && (
        <div className="rounded-lg border border-[hsl(var(--fail)/0.3)] bg-[hsl(var(--fail)/0.06)] p-4 text-sm text-[hsl(var(--fail))]">
          <p className="font-semibold">Processing failed</p>
          <p className="mt-1">{call.status_detail}</p>
        </div>
      )}

      {/* ── Two-column layout ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">

        {/* ── Left / main column ── */}
        <div className="flex flex-col gap-4 lg:col-span-7">

          {/* 1. Overall score hero (when scored) */}
          {isScored && analysis && (
            <OverallScoreHero
              analysis={analysis}
              durationSeconds={call.duration_seconds}
            />
          )}

          {/* 2. Escalation banner */}
          {isScored && analysis?.escalate_for_review && (
            <EscalationBanner reason={analysis.escalation_reason ?? null} />
          )}

          {/* 3. Scorecard — all dimensions */}
          <ScorecardPanel
            callId={callId}
            callStatus={call.status as CallStatus}
            segments={segments}
            onEvidenceClick={handleEvidenceClick}
          />

          {/* 4. Summary & actions (when scored) */}
          {isScored && analysis && (
            <SummaryActionsCard
              analysis={analysis}
              segments={segments}
              onMomentClick={handleEvidenceClick}
            />
          )}

          {/* 5. Conversation dynamics (when scored) */}
          {isScored && analysis && (
            <ConversationDynamics analysis={analysis} />
          )}

          {/* 6. Agent run trace (when scored) */}
          {isScored && trace && <AgentRunTrace trace={trace} />}
        </div>

        {/* ── Right / sticky column: audio + transcript ── */}
        <div className="flex flex-col gap-4 lg:col-span-5 lg:self-start lg:sticky lg:top-4">
          {hasTranscript && audioUrl && (
            <AudioPlayer
              ref={audioPlayerRef}
              src={audioUrl}
              onTimeUpdate={setCurrentTimeSec}
            />
          )}
          {hasTranscript && (
            <TranscriptPanel
              segments={segments}
              currentTimeSec={currentTimeSec}
              onSeek={handleSeek}
              focusedSegmentId={focusedSegmentId ?? undefined}
              entitiesRedacted={transcript?.entities_redacted}
              redactionProvider={transcript?.redaction_provider}
              className="max-h-[60vh]"
            />
          )}
        </div>
      </div>
    </div>
  );
}
