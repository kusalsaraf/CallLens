const agents = [
  { name: "Empathy", color: "bg-quality/10 text-quality border-quality/20" },
  { name: "Resolution", color: "bg-quality/10 text-quality border-quality/20" },
  { name: "Compliance", color: "bg-primary/10 text-primary border-primary/20" },
  { name: "Tone", color: "bg-at-risk/10 text-at-risk border-at-risk/20" },
  { name: "Rubric", color: "bg-muted text-muted-foreground border-border" },
];

export function MultiAgentExplainer() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-6xl md:grid md:grid-cols-2 md:gap-20 md:items-center">
        {/* Text */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-primary">
            Architecture
          </p>
          <h2 className="font-display text-4xl font-bold leading-tight text-foreground">
            Five specialists.
            <br />
            One calibrated score.
          </h2>
          <p className="mt-5 text-muted-foreground leading-relaxed">
            Specialist agents each evaluate a single dimension — empathy,
            resolution, compliance, tone, and rubric adherence. A supervisor
            agent synthesizes their findings into a unified quality score,
            weighted by your priorities.
          </p>
          <p className="mt-4 text-muted-foreground leading-relaxed">
            No single model sees the whole problem. Specialization means higher
            accuracy on each dimension and clear provenance for every finding.
          </p>
        </div>

        {/* Diagram */}
        <div className="mt-12 md:mt-0">
          <div className="flex flex-col items-center gap-4">
            {/* Specialist row */}
            <div className="flex flex-wrap justify-center gap-2">
              {agents.map(({ name, color }) => (
                <div
                  key={name}
                  className={`rounded-full border px-3 py-1 text-xs font-semibold ${color}`}
                >
                  {name}
                </div>
              ))}
            </div>

            {/* Arrow */}
            <div className="flex flex-col items-center gap-1 text-muted-foreground/40">
              <div className="h-6 w-px bg-border" />
              <svg width="12" height="8" viewBox="0 0 12 8" fill="none">
                <path
                  d="M1 1l5 5 5-5"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            {/* Supervisor */}
            <div className="rounded-xl border border-primary/30 bg-primary/5 px-6 py-4 text-center">
              <p className="text-xs font-semibold uppercase tracking-widest text-primary">
                Supervisor Agent
              </p>
              <p className="tabular mt-2 font-display text-4xl font-bold text-foreground">
                87
                <span className="text-lg font-normal text-muted-foreground">
                  /100
                </span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Calibrated quality score
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
