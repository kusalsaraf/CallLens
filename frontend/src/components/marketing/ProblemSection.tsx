export function ProblemSection() {
  const pains = [
    {
      stat: "98%",
      label: "of calls never reviewed",
      desc: "Manual QA teams can only sample a tiny fraction — the rest are invisible.",
    },
    {
      stat: "6–8 wks",
      label: "to detect a coaching gap",
      desc: "By the time patterns emerge from spot checks, customers have already felt the impact.",
    },
    {
      stat: "$0",
      label: "trend data from unreviewed calls",
      desc: "No data means no accountability, no benchmarking, no proof of improvement.",
    },
  ];

  return (
    <section className="border-y border-border bg-muted/30 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 max-w-xl">
          <h2 className="font-display text-4xl font-bold leading-tight text-foreground">
            The 2% problem
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Your QA team works hard — but manual review only reaches a fraction
            of calls. The remaining 98% are a blind spot you&apos;re paying for every
            day.
          </p>
        </div>

        <div className="grid gap-8 md:grid-cols-3">
          {pains.map(({ stat, label, desc }) => (
            <div key={stat} className="border-l-2 border-fail/40 pl-5">
              <p className="tabular font-display text-5xl font-bold text-fail">
                {stat}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {label}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
