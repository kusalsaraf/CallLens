"use client";

import { useEffect, useImperativeHandle, useRef, useState } from "react";
import { cn, formatDuration } from "@/lib/utils";

export interface AudioPlayerRef {
  seekTo: (seconds: number) => void;
}

interface AudioPlayerProps {
  src: string;
  onTimeUpdate?: (seconds: number) => void;
  className?: string;
  ref?: React.Ref<AudioPlayerRef>;
}

export function AudioPlayer({
  src,
  onTimeUpdate,
  className,
  ref,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [rate, setRate] = useState(1);

  useImperativeHandle(ref, () => ({
    seekTo: (seconds: number) => {
      if (audioRef.current) audioRef.current.currentTime = seconds;
    },
  }));

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = rate;
  }, [rate]);

  function handleTimeUpdate() {
    const t = audioRef.current?.currentTime ?? 0;
    setCurrentTime(t);
    onTimeUpdate?.(t);
  }

  function togglePlay() {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      void audioRef.current.play();
    }
  }

  function handleSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const t = parseFloat(e.target.value);
    if (audioRef.current) audioRef.current.currentTime = t;
    setCurrentTime(t);
    onTimeUpdate?.(t);
  }

  const RATES = [1, 1.5, 2] as const;

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border bg-card p-4",
        className,
      )}
    >
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={() =>
          setDuration(audioRef.current?.duration ?? 0)
        }
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />

      {/* Progress row */}
      <div className="flex items-center gap-3">
        <button
          onClick={togglePlay}
          aria-label={isPlaying ? "Pause" : "Play"}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm text-primary-foreground transition-transform hover:scale-105 active:scale-95"
        >
          {isPlaying ? "⏸" : "▶"}
        </button>

        <input
          type="range"
          min={0}
          max={duration || 1}
          step={0.1}
          value={currentTime}
          onChange={handleSeek}
          aria-label="Audio progress"
          className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-muted accent-primary"
        />

        <span className="tabular shrink-0 text-xs text-muted-foreground">
          {formatDuration(currentTime)} /{" "}
          {duration ? formatDuration(duration) : "--:--"}
        </span>
      </div>

      {/* Playback rate */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground">Speed</span>
        {RATES.map((r) => (
          <button
            key={r}
            onClick={() => setRate(r)}
            className={cn(
              "rounded px-2 py-0.5 text-xs font-medium tabular transition-colors",
              rate === r
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            {r}×
          </button>
        ))}
      </div>
    </div>
  );
}
