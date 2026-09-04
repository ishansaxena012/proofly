import type { Metadata } from "next";

import { StartResearchForm } from "@/components/research/start-research-form";

export const metadata: Metadata = {
  title: "Start research",
  description:
    "Name one specific product and Proofly will gather sources, extract evidence, verify claims and produce a cited report.",
};

const WHAT_HAPPENS = [
  {
    title: "It takes a few minutes",
    body: "The job runs through nine stages. You'll watch each one report what it actually found — including channels that come back empty.",
  },
  {
    title: "You can leave and come back",
    body: "Progress is persisted server-side. The live timeline replays its full history when you reopen the page.",
  },
  {
    title: "The report is the deliverable",
    body: "When the job finishes you get one report, with every claim expandable down to the evidence and source URL behind it.",
  },
];

export default function ResearchPage() {
  return (
    <div className="container max-w-3xl py-14 sm:py-20">
      <header className="mb-10">
        <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
          New research job
        </p>
        <h1 className="display mt-4 text-4xl font-semibold">Research a product</h1>
        <p className="prose-readable mt-4">
          Proofly will resolve your query to one canonical product, gather independent
          sources across the web, Reddit and YouTube, extract structured evidence, verify
          each generated claim against it, and produce a report you can audit line by line.
        </p>
      </header>

      <StartResearchForm />

      <section className="mt-14">
        <h2 className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
          What happens next
        </h2>
        <dl className="mt-5 grid gap-6 sm:grid-cols-3">
          {WHAT_HAPPENS.map(({ title, body }) => (
            <div key={title} className="border-t border-border pt-4">
              <dt className="text-sm font-semibold">{title}</dt>
              <dd className="mt-1.5 text-sm leading-6 text-muted-foreground">{body}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
