const steps = [
  {
    n: "01",
    title: "Upload",
    desc: "Drop in recordings or connect your call center platform. CallLens accepts MP3, WAV, and M4A out of the box.",
  },
  {
    n: "02",
    title: "Analyze",
    desc: "Each call is transcribed, speakers diarized, then five specialist AI agents evaluate it in parallel against your rubric.",
  },
  {
    n: "03",
    title: "Act",
    desc: "Dashboards surface scores, trends, and coaching insights in real time. Filter by agent, team, date, or rubric dimension.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-14">
          <h2 className="font-display text-4xl font-bold text-foreground">
            How it works
          </h2>
          <p className="mt-3 max-w-lg text-muted-foreground">
            Three steps from raw recording to actionable quality data.
          </p>
        </div>

        <div className="grid gap-12 md:grid-cols-3">
          {steps.map(({ n, title, desc }) => (
            <div key={n} className="group relative">
              {/* Connector line (desktop) */}
              <div className="absolute left-0 top-7 hidden h-px w-full bg-border md:block [&:last-child]:hidden" />

              <div className="relative">
                <span className="font-display text-6xl font-bold text-border">
                  {n}
                </span>
                <h3 className="mt-2 text-lg font-semibold text-foreground">
                  {title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
