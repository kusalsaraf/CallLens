import { cn } from "@/lib/utils";
import type { CallStatus } from "@/lib/api/calls";

interface StatusBadgeProps {
  status: CallStatus;
  className?: string;
}

const CONFIG: Record<
  CallStatus,
  { label: string; classes: string; pulse?: boolean }
> = {
  uploaded: {
    label: "Uploaded",
    classes: "bg-muted text-muted-foreground",
  },
  transcribing: {
    label: "Transcribing",
    classes: "bg-[hsl(var(--at-risk)/0.12)] text-[hsl(var(--at-risk))]",
    pulse: true,
  },
  diarizing: {
    label: "Diarizing",
    classes: "bg-[hsl(var(--at-risk)/0.12)] text-[hsl(var(--at-risk))]",
    pulse: true,
  },
  transcribed: {
    label: "Transcribed",
    classes: "bg-[hsl(var(--quality)/0.12)] text-[hsl(var(--quality))]",
  },
  failed: {
    label: "Failed",
    classes: "bg-[hsl(var(--fail)/0.12)] text-[hsl(var(--fail))]",
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const cfg = CONFIG[status] ?? CONFIG.uploaded;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
        cfg.classes,
        className,
      )}
    >
      {cfg.pulse && (
        <span className="h-1.5 w-1.5 animate-pulse-slow rounded-full bg-current" />
      )}
      {cfg.label}
    </span>
  );
}
