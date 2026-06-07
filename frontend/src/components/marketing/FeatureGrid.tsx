const features = [
  {
    icon: "◎",
    title: "Evidence-linked scores",
    desc: "Every score is tied to a timestamp and transcript excerpt. No black boxes — click any dimension to see exactly why it scored that way.",
  },
  {
    icon: "⊛",
    title: "Compliance monitoring",
    desc: "Required disclosures, prohibited language, and regulatory adherence tracked automatically on every call — not just the ones you happened to audit.",
  },
  {
    icon: "↗",
    title: "Coaching insights",
    desc: "Specific, actionable feedback generated per agent, per call. Pinpoint the moment an empathy opportunity was missed, not just that the score was low.",
  },
  {
    icon: "⌕",
    title: "Semantic search",
    desc: 'Find every call where an agent said "I guarantee" or where a customer expressed frustration — across thousands of recordings in seconds.',
  },
  {
    icon: "◻",
    title: "Custom rubrics",
    desc: "Define what good looks like for your operation — industry standards, brand voice, escalation criteria. CallLens scores to your exact standard.",
  },
  {
    icon: "⌇",
    title: "Trend analytics",
    desc: "Track quality over time, by team, agent, or rubric dimension. Know exactly where to focus coaching next quarter before it shows up in CSAT.",
  },
];

export function FeatureGrid() {
  return (
    <section id="features" className="border-t border-border bg-muted/20 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-14">
          <h2 className="font-display text-4xl font-bold text-foreground">
            Everything you need
          </h2>
          <p className="mt-3 max-w-lg text-muted-foreground">
            Built for quality and compliance teams who need answers, not another
            dashboard to maintain.
          </p>
        </div>

        <div className="grid gap-px border border-border bg-border md:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon, title, desc }) => (
            <div
              key={title}
              className="group bg-background p-7 transition-colors hover:bg-primary/[0.03]"
            >
              <span className="font-display text-2xl text-primary">{icon}</span>
              <h3 className="mt-3 text-sm font-semibold text-foreground">
                {title}
              </h3>
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
