import { Button } from "@/components/ui/button";

export default function OverviewPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      {/* Empty state illustration */}
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/50">
        <span className="font-display text-4xl text-muted-foreground/50">◎</span>
      </div>

      <h2 className="font-display text-2xl font-bold text-foreground">
        No calls yet
      </h2>
      <p className="mt-2 max-w-xs text-sm leading-relaxed text-muted-foreground">
        Upload your first recording and CallLens will transcribe, score, and
        surface insights within minutes.
      </p>

      <Button className="mt-6" disabled>
        Upload recording
        <span className="ml-2 rounded-full bg-primary-foreground/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
          coming soon
        </span>
      </Button>
    </div>
  );
}
