import Link from "next/link";
import { Button } from "@/components/ui/button";

const dimensions = [
  { label: "Empathy", score: 94, color: "bg-quality" },
  { label: "Resolution", score: 88, color: "bg-quality" },
  { label: "Compliance", score: 85, color: "bg-primary" },
  { label: "Tone", score: 72, color: "bg-at-risk" },
];

function ScoreCard() {
  return (
    <div className="relative w-full max-w-[340px] rounded-2xl border border-border bg-card p-6 shadow-lg shadow-foreground/5">
      {/* Header row */}
      <div className="mb-5 flex items-start justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Quality Score
          </p>
          <p className="tabular mt-1 font-display text-5xl font-bold leading-none text-foreground">
            87
            <span className="text-2xl font-normal text-muted-foreground">/100</span>
          </p>
        </div>
        {/* Radial indicator */}
        <div className="flex h-12 w-12 items-center justify-center rounded-full border-[3px] border-quality/30 bg-quality/10">
          <div className="h-5 w-5 rounded-full bg-quality" />
        </div>
      </div>

      {/* Dimension bars */}
      <div className="space-y-2.5">
        {dimensions.map(({ label, score, color }) => (
          <div key={label} className="flex items-center gap-3">
            <span className="w-[72px] shrink-0 text-xs text-muted-foreground">
              {label}
            </span>
            <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
              <div
                className={`h-full rounded-full ${color} transition-all duration-700`}
                style={{ width: `${score}%` }}
              />
            </div>
            <span className="tabular w-6 text-right text-xs font-medium text-foreground">
              {score}
            </span>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-5 flex items-center justify-between border-t border-border pt-4">
        <span className="text-[10px] text-muted-foreground">
          Call&nbsp;#A-4821 · 14m 32s
        </span>
        <span className="inline-flex items-center gap-1 rounded-full bg-quality/10 px-2 py-0.5 text-[10px] font-semibold text-quality">
          ● Scored
        </span>
      </div>
    </div>
  );
}

export function Hero() {
  return (
    <section className="relative flex min-h-[90vh] flex-col items-center justify-center overflow-hidden px-6 pt-20">
      {/* Subtle grain texture */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
          backgroundSize: "200px 200px",
        }}
      />

      <div className="relative mx-auto grid max-w-6xl gap-16 md:grid-cols-[1fr_auto] md:items-center">
        {/* Left: editorial text */}
        <div>
          <p
            className="animate-fade-up delay-100 mb-4 inline-block rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primary"
            style={{ opacity: 0 }}
          >
            AI Call Analytics
          </p>

          <h1
            className="animate-fade-up delay-200 font-display text-[3.5rem] font-bold leading-[1.08] tracking-tight text-foreground md:text-[4.5rem]"
            style={{ opacity: 0 }}
          >
            Score every call.
            <br />
            <em className="not-italic text-primary">Not a sample.</em>
          </h1>

          <p
            className="animate-fade-up delay-300 mt-6 max-w-[520px] text-lg leading-relaxed text-muted-foreground"
            style={{ opacity: 0 }}
          >
            CallLens uses multi-agent AI to evaluate 100% of customer
            conversations — surfacing coaching gaps, compliance risks, and
            quality trends across your entire operation.
          </p>

          <div
            className="animate-fade-up delay-400 mt-8 flex flex-wrap items-center gap-3"
            style={{ opacity: 0 }}
          >
            <Button size="lg" asChild>
              <Link href="/signup">Get early access</Link>
            </Button>
            <Button variant="outline" size="lg" asChild>
              <Link href="#how-it-works">See how it works</Link>
            </Button>
          </div>

          <p
            className="animate-fade-up delay-500 mt-5 text-sm text-muted-foreground"
            style={{ opacity: 0 }}
          >
            Single-user · no credit card required · setup in 5 minutes
          </p>
        </div>

        {/* Right: score card mockup */}
        <div
          className="animate-fade-up delay-300 hidden md:block"
          style={{ opacity: 0 }}
        >
          <ScoreCard />
        </div>
      </div>

      {/* Bottom scroll cue */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce text-muted-foreground/40">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path
            d="M10 4v12M4 10l6 6 6-6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </section>
  );
}
