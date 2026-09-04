import Link from "next/link";
import {
  ArrowRight,
  FileText,
  Layers,
  ListChecks,
  Quote,
  ScanSearch,
  ShieldCheck,
  Split,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const PIPELINE = [
  {
    icon: ScanSearch,
    step: "01",
    title: "Resolve the product",
    body: "Your query is pinned to one canonical product — brand, model, category — so every later step is researching the same thing, not a family of lookalikes.",
  },
  {
    icon: Layers,
    step: "02",
    title: "Gather independent sources",
    body: "Professional reviews and documentation from the web, first-hand owner reports from Reddit, and transcript-level detail from YouTube. Near-duplicate and syndicated coverage is clustered so one story repeated ten times doesn't count ten times.",
  },
  {
    icon: Quote,
    step: "03",
    title: "Extract evidence, not summaries",
    body: "Each fetched document is split into passages, and every piece of evidence is typed — measurement, expert opinion, customer experience, specification — and stays attached to the passage and URL it came from.",
  },
  {
    icon: ListChecks,
    step: "04",
    title: "Generate claims",
    body: "Evidence is grouped into candidate claims per topic. Evidence that disagrees is attached to the same claim rather than discarded for being inconvenient.",
  },
  {
    icon: ShieldCheck,
    step: "05",
    title: "Verify and score confidence",
    body: "Every claim is checked back against its evidence. Confidence reflects the quality, quantity and independence of that evidence — not how fluent the model sounds. “Insufficient evidence” is a valid outcome.",
  },
  {
    icon: FileText,
    step: "06",
    title: "Produce the report",
    body: "One report: verdict, category scores, strengths, weaknesses, long-term ownership, who should avoid it. The overall score is derived from verified claims. Every line expands down to its evidence and source.",
  },
];

const PRINCIPLES = [
  {
    icon: Split,
    title: "Disagreement is preserved",
    body: "When reviewers contradict each other, Proofly shows both positions with their sources and explains the likely reason — it never averages a real disagreement into a comfortable middle.",
  },
  {
    icon: ShieldCheck,
    title: "Confidence is earned",
    body: "Thin, duplicated or dependent evidence produces low confidence, and the report says so. A report that admits it doesn't know is more useful than one that guesses.",
  },
  {
    icon: Quote,
    title: "Nothing is a dead end",
    body: "Claim → evidence → passage → original URL. Every assertion in the report can be opened until you reach a link you can check yourself.",
  },
];

export default function LandingPage() {
  return (
    <>
      {/* Hero */}
      <section className="border-b border-border">
        <div className="container grid gap-12 py-20 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-center lg:py-28">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
              AI product research agent
            </p>
            <h1 className="display mt-5 text-4xl font-semibold leading-[1.08] sm:text-5xl lg:text-[3.4rem]">
              Research one product properly,
              <br className="hidden sm:block" /> and show the evidence.
            </h1>
            <p className="prose-readable mt-6 max-w-xl text-base">
              Name a specific product. Proofly gathers independent sources, extracts
              structured evidence, generates claims, verifies each one against that
              evidence, and hands you a report where every sentence traces back to
              something you can read for yourself.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Button size="lg" asChild>
                <Link href="/research">
                  Research a product
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="#how-it-works">See how it works</Link>
              </Button>
            </div>
            <p className="mt-5 text-sm text-muted-foreground">
              One product, one job, one report. No comparison tables, no shopping links, no
              recommendations we can&apos;t defend.
            </p>
          </div>

          {/* An honest sketch of the report structure, not a fake dashboard. */}
          <Card className="lg:justify-self-end lg:shadow-none">
            <CardContent className="p-0">
              <div className="border-b border-border px-6 py-5">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  What a Proofly report contains
                </p>
              </div>
              <dl className="divide-y divide-border text-sm">
                {[
                  ["Verdict", "A single stated position, with its caveats attached"],
                  ["Overall score", "Derived from verified claims — never model-invented"],
                  ["Confidence", "A measure of evidence quality, shown next to every score"],
                  ["Category scores", "Per-dimension, each with its own confidence"],
                  ["Conflicting opinions", "Both positions, both sets of sources, unresolved"],
                  ["Long-term ownership", "What owners report after the honeymoon period"],
                  ["Who should avoid it", "Stated plainly, not buried"],
                  ["Sources", "Every URL used, grouped by channel"],
                ].map(([term, detail]) => (
                  <div key={term} className="flex flex-col gap-1 px-6 py-3.5">
                    <dt className="font-medium">{term}</dt>
                    <dd className="text-muted-foreground">{detail}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Pipeline */}
      <section id="how-it-works" className="container scroll-mt-20 py-20">
        <div className="max-w-2xl">
          <h2 className="display text-3xl font-semibold sm:text-4xl">How it works</h2>
          <p className="prose-readable mt-4">
            Proofly never goes straight from a web search to an answer. The pipeline is
            fixed, and you watch it run in real time — each stage reports what it actually
            found, including when a channel returns nothing.
          </p>
        </div>

        <ol className="mt-12 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {PIPELINE.map(({ icon: Icon, step, title, body }) => (
            <li key={step} className="flex flex-col gap-3 bg-card p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-accent-foreground">
                  <Icon aria-hidden="true" className="h-4 w-4" />
                </span>
                <span className="font-mono text-xs text-muted-foreground">{step}</span>
              </div>
              <h3 className="text-base font-semibold leading-snug">{title}</h3>
              <p className="text-sm leading-6 text-muted-foreground">{body}</p>
            </li>
          ))}
        </ol>

        <p className="mt-6 font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
          sources → passages → evidence → claims → verification → report
        </p>
      </section>

      <Separator />

      {/* Principles */}
      <section className="container py-20">
        <div className="max-w-2xl">
          <h2 className="display text-3xl font-semibold sm:text-4xl">
            What makes the report trustworthy
          </h2>
          <p className="prose-readable mt-4">
            Three rules are enforced by the system, not by tone of voice.
          </p>
        </div>
        <div className="mt-12 grid gap-8 md:grid-cols-3">
          {PRINCIPLES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="border-t-2 border-foreground/80 pt-5">
              <Icon aria-hidden="true" className="h-5 w-5 text-foreground" />
              <h3 className="mt-3 text-base font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-y border-border bg-secondary/60">
        <div className="container flex flex-col items-start gap-6 py-16 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="display text-2xl font-semibold sm:text-3xl">
              Start with a specific product
            </h2>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              &ldquo;Sony WH-1000XM6&rdquo; works. &ldquo;Best headphones&rdquo; does not —
              Proofly researches one product, not a category.
            </p>
          </div>
          <Button size="lg" asChild>
            <Link href="/research">
              Research a product
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </section>
    </>
  );
}
