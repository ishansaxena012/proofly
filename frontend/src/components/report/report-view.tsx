"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, Clock, Hourglass } from "lucide-react";

import { ConfidenceMeter, ScoreDial, confidenceLabel } from "@/components/common/measures";
import { DemoModeBadge, DemoModeBanner } from "@/components/common/demo-mode-banner";
import { EmptyState, ErrorState } from "@/components/common/states";
import { JobStatusBadge } from "@/components/common/status-badge";
import { ClaimLedger, FindingDisclosure } from "@/components/report/claim-disclosure";
import { FollowUpPanel } from "@/components/report/follow-up-panel";
import { ReportDataProvider } from "@/components/report/report-context";
import {
  AudienceList,
  CaveatList,
  CategoryScores,
  ConfidenceExplainer,
  ConflictList,
  PointList,
  ReportSection,
} from "@/components/report/report-sections";
import { EvidenceDisclosure } from "@/components/report/evidence-disclosure";
import { SourcesPanel } from "@/components/research/sources-panel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ReportNotReadyError } from "@/lib/api";
import { useEvidence, useReport, useResearchJob, useSources } from "@/lib/queries";
import type { Report, ResearchSource } from "@/lib/types";
import { formatDate, humanizeEnum } from "@/lib/utils";

const NAV_SECTIONS = [
  { id: "verdict", label: "Verdict" },
  { id: "categories", label: "Category scores" },
  { id: "strengths", label: "Strengths & weaknesses" },
  { id: "findings", label: "Key findings" },
  { id: "sentiment", label: "Praise & complaints" },
  { id: "conflicts", label: "Conflicting opinions" },
  { id: "ownership", label: "Long-term ownership" },
  { id: "audience", label: "Who it's for" },
  { id: "caveats", label: "Caveats" },
  { id: "claims", label: "All claims" },
  { id: "sources", label: "Sources" },
  { id: "followup", label: "Ask a follow-up" },
];

export function ReportView({ researchJobId }: { researchJobId: string }) {
  const jobQuery = useResearchJob(researchJobId);
  const reportQuery = useReport(researchJobId);
  const sourcesQuery = useSources(researchJobId, { enabled: reportQuery.isSuccess });
  const evidenceQuery = useEvidence(researchJobId, undefined, {
    enabled: reportQuery.isSuccess,
  });

  if (reportQuery.isLoading) return <ReportSkeleton />;

  if (reportQuery.isError) {
    const error = reportQuery.error;
    if (error instanceof ReportNotReadyError) {
      return (
        <div className="container max-w-3xl py-16">
          <Alert variant="info">
            <Hourglass aria-hidden="true" />
            <AlertTitle>The report isn&apos;t ready yet</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>
                This job is currently{" "}
                <span className="font-medium">
                  {humanizeEnum(error.jobStatus ?? jobQuery.data?.status ?? "")}
                </span>
                . A report is only produced once the pipeline finishes — nothing is written
                from partial evidence.
              </p>
              <Button size="sm" asChild>
                <Link href={`/research/${researchJobId}`}>
                  <ArrowLeft aria-hidden="true" />
                  Watch the pipeline
                </Link>
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      );
    }

    return (
      <div className="container max-w-3xl py-16">
        <ErrorState
          context="report"
          error={error}
          onRetry={() => void reportQuery.refetch()}
        />
      </div>
    );
  }

  const report = reportQuery.data;
  if (!report) {
    return (
      <div className="container max-w-3xl py-16">
        <EmptyState
          title="Empty report"
          description="The backend returned no report body for this job."
        />
      </div>
    );
  }

  const job = jobQuery.data;
  const productName =
    job?.product?.canonicalName || job?.product?.rawQuery || "This product";
  const partial = job?.status === "PARTIALLY_COMPLETED";
  const demoMode = report.demoMode || Boolean(job?.demoMode);

  return (
    <ReportDataProvider
      report={report}
      evidence={evidenceQuery.data}
      sources={sourcesQuery.data}
      evidenceLoading={evidenceQuery.isLoading}
    >
      <article className="container max-w-6xl py-10 sm:py-14">
        <ReportHeader
          report={report}
          productName={productName}
          demoMode={demoMode}
          subtitle={
            job?.product
              ? [job.product.brand, job.product.model, job.product.category]
                  .filter(Boolean)
                  .join(" · ")
              : null
          }
          statusBadge={job ? <JobStatusBadge status={job.status} /> : null}
          generatedAt={job?.completedAt ?? null}
          researchJobId={researchJobId}
        />

        {demoMode ? <DemoModeBanner className="mt-6" /> : null}

        {partial ? (
          <Alert variant="warning" className="mt-6">
            <Clock aria-hidden="true" />
            <AlertTitle>Produced from a partially completed run</AlertTitle>
            <AlertDescription>
              At least one research channel or pipeline stage degraded. This report is built
              only from the evidence that was actually gathered — read the caveats section
              before relying on it.
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="mt-10 gap-12 lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:items-start">
          <ReportNav />

          <div className="min-w-0 space-y-12">
            <VerdictSection report={report} />

            <ReportSection
              id="categories"
              title="Category scores"
              description="Each dimension is scored independently and carries its own confidence, because the evidence behind them is not equally strong."
            >
              <CategoryScores items={report.categoryScores ?? []} />
            </ReportSection>

            <ReportSection
              id="strengths"
              title="Strengths & weaknesses"
              description="Expand any point to read the evidence it rests on, and follow that through to the original source."
            >
              <div className="grid gap-10 lg:grid-cols-2">
                <div>
                  <h3 className="mb-4 text-xs font-medium uppercase tracking-[0.16em] text-positive">
                    Key strengths
                  </h3>
                  <PointList
                    points={report.keyStrengths ?? []}
                    tone="positive"
                    label="strength"
                  />
                </div>
                <div>
                  <h3 className="mb-4 text-xs font-medium uppercase tracking-[0.16em] text-negative">
                    Key weaknesses
                  </h3>
                  <PointList
                    points={report.keyWeaknesses ?? []}
                    tone="negative"
                    label="weakness"
                  />
                </div>
              </div>
            </ReportSection>

            <ReportSection
              id="findings"
              title="Key findings"
              description="Each finding is generated from a single verified claim. Trace it to see that claim's status, confidence, and every piece of evidence for and against it."
            >
              {(report.keyFindings ?? []).length === 0 ? (
                <EmptyState
                  title="No key findings"
                  description="No claim reached the threshold required to be stated as a finding."
                />
              ) : (
                <ul className="rounded-lg border border-border bg-card px-5 py-4">
                  {report.keyFindings.map((finding, index) => (
                    <FindingDisclosure
                      key={`${finding.claimId ?? "finding"}-${index}`}
                      text={finding.text}
                      claimId={finding.claimId}
                    />
                  ))}
                </ul>
              )}
            </ReportSection>

            <ReportSection
              id="sentiment"
              title="What owners keep saying"
              description="Recurring themes across first-hand reports — repeated independently, not repeated by one source quoted many times."
            >
              <div className="grid gap-10 lg:grid-cols-2">
                <div>
                  <h3 className="mb-4 text-xs font-medium uppercase tracking-[0.16em] text-positive">
                    Common praise
                  </h3>
                  <PointList
                    points={report.commonPraise ?? []}
                    tone="praise"
                    label="praise"
                  />
                </div>
                <div>
                  <h3 className="mb-4 text-xs font-medium uppercase tracking-[0.16em] text-negative">
                    Common complaints
                  </h3>
                  <PointList
                    points={report.commonComplaints ?? []}
                    tone="complaint"
                    label="complaint"
                  />
                </div>
              </div>
            </ReportSection>

            <ReportSection
              id="conflicts"
              title="Conflicting opinions"
              description="Where the sources disagree, both positions are kept. Proofly does not resolve a genuine disagreement by majority vote or by averaging it away."
              aside={
                (report.conflicts ?? []).length > 0 ? (
                  <Badge variant="caution">
                    {report.conflicts.filter((c) => !c.resolved).length} unresolved
                  </Badge>
                ) : null
              }
            >
              <ConflictList conflicts={report.conflicts ?? []} />
            </ReportSection>

            <ReportSection
              id="ownership"
              title="Long-term ownership"
              description="What owners report after the first few weeks — durability, support, and the problems that only appear with time."
            >
              {report.longTermOwnership?.text ? (
                <Card>
                  <CardContent className="p-6">
                    <EvidenceDisclosure
                      evidenceIds={report.longTermOwnership.evidenceIds ?? []}
                      label="long-term ownership"
                    >
                      <p className="prose-readable">{report.longTermOwnership.text}</p>
                    </EvidenceDisclosure>
                  </CardContent>
                </Card>
              ) : (
                <EmptyState
                  title="No long-term ownership evidence"
                  description="No source in this run reported extended ownership experience. Treat durability and support as unknown rather than fine."
                />
              )}
            </ReportSection>

            <ReportSection
              id="audience"
              title="Who this is for"
              description="Stated in both directions. A product being good is not the same as it being right for you."
            >
              <div className="grid gap-10 lg:grid-cols-2">
                <div>
                  <h3 className="mb-4 text-xs font-medium uppercase tracking-[0.16em] text-positive">
                    Who should buy it
                  </h3>
                  <AudienceList
                    items={report.whoShouldBuy ?? []}
                    tone="buy"
                    emptyMessage="The evidence did not support a clear recommendation for any particular buyer."
                  />
                </div>
                <div>
                  <h3 className="mb-4 text-xs font-medium uppercase tracking-[0.16em] text-negative">
                    Who should avoid it
                  </h3>
                  <AudienceList
                    items={report.whoShouldAvoid ?? []}
                    tone="avoid"
                    emptyMessage="No group was identified as clearly poorly served by this product."
                  />
                </div>
              </div>
            </ReportSection>

            <ReportSection
              id="caveats"
              title="Caveats & limitations"
              description="What this report could not establish, and why. Read this before acting on anything above."
            >
              <CaveatList caveats={report.caveats ?? []} />
            </ReportSection>

            <ReportSection
              id="claims"
              title="All claims"
              description="The complete audit trail. Every claim generated during this run, its verification status, its confidence, and all evidence for and against it."
              aside={
                <span className="font-mono text-xs text-muted-foreground">
                  {(report.claims ?? []).length} claims
                </span>
              }
            >
              {(report.claims ?? []).length === 0 ? (
                <EmptyState
                  title="No claims recorded"
                  description="This report contains no claim records, so nothing above can be traced further."
                />
              ) : (
                <ClaimLedger claims={report.claims} />
              )}
            </ReportSection>

            <ReportSection
              id="sources"
              title="Sources"
              description="Every source used in this run, grouped by channel. Failed and skipped fetches are listed too — omitting them would overstate the evidence base."
              aside={
                <span className="font-mono text-xs text-muted-foreground">
                  {(sourcesQuery.data ?? report.sources ?? []).length} sources
                </span>
              }
            >
              {sourcesQuery.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-20 w-full" />
                  <Skeleton className="h-20 w-full" />
                </div>
              ) : (
                <SourcesPanel sources={resolveSourceList(report, sourcesQuery.data)} />
              )}
              {sourcesQuery.isError ? (
                <p className="mt-4 text-sm text-muted-foreground">
                  Extended source metadata (authority, first-hand, independence clustering)
                  could not be loaded; the list above comes from the report itself.
                </p>
              ) : null}
            </ReportSection>

            <ReportSection
              id="followup"
              title="Ask a follow-up"
              description="Questions are answered from this job's evidence only — no new research, no unsupported facts."
            >
              <FollowUpPanel researchJobId={researchJobId} />
            </ReportSection>
          </div>
        </div>

        <footer className="mt-16 border-t border-border pt-6">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/research/${researchJobId}`}>
              <ArrowLeft aria-hidden="true" />
              Back to the pipeline for this job
            </Link>
          </Button>
        </footer>
      </article>
    </ReportDataProvider>
  );
}

/** Prefer the richer sources endpoint; fall back to the report's own list. */
function resolveSourceList(
  report: Report,
  sources: ResearchSource[] | undefined,
): ResearchSource[] {
  if (sources && sources.length > 0) return sources;
  return (report.sources ?? []).map((source) => ({
    id: source.id,
    channel: source.channel ?? "WEB",
    url: source.url,
    title: source.title,
    sourceType: source.sourceType,
    authorityScore: null,
    firstHand: null,
    independenceGroupId: null,
    status: "FETCHED",
  }));
}

function ReportHeader({
  report,
  productName,
  subtitle,
  demoMode,
  statusBadge,
  generatedAt,
  researchJobId,
}: {
  report: Report;
  productName: string;
  subtitle: string | null;
  demoMode: boolean;
  statusBadge: React.ReactNode;
  generatedAt: string | null;
  researchJobId: string;
}) {
  return (
    <header>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
          Research report
        </span>
        {demoMode ? <DemoModeBadge /> : null}
        {statusBadge}
        <span className="ml-auto font-mono text-xs text-muted-foreground">
          {researchJobId}
        </span>
      </div>

      <h1 className="display mt-4 text-4xl font-semibold leading-tight sm:text-5xl">
        {productName}
      </h1>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm text-muted-foreground">
        {subtitle ? <span>{subtitle}</span> : null}
        {generatedAt ? <span>Generated {formatDate(generatedAt)}</span> : null}
        <span>
          {(report.sources ?? []).length} sources · {(report.claims ?? []).length} claims
        </span>
      </div>
    </header>
  );
}

function VerdictSection({ report }: { report: Report }) {
  return (
    <section id="verdict" className="scroll-mt-24">
      <div className="grid gap-8 rounded-lg border border-border bg-card p-6 sm:p-8 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-start lg:gap-12">
        <div className="flex flex-col items-center gap-4">
          <ScoreDial score={report.overallScore} />
          <p className="max-w-[16rem] text-center text-xs leading-5 text-muted-foreground">
            Derived from verified claims and their evidence quality — not produced by the
            model as a free-form opinion.
          </p>
        </div>

        <div className="min-w-0 space-y-6">
          <div>
            <h2 className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Verdict
            </h2>
            <p className="display mt-2 text-2xl font-semibold leading-snug sm:text-3xl">
              {report.verdict ?? "No verdict could be stated from the available evidence."}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              {confidenceLabel(report.confidence)} overall.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-[minmax(0,1fr)_240px]">
            <div>
              <h3 className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Executive summary
              </h3>
              <p className="prose-readable mt-2">
                {report.executiveSummary ??
                  "No executive summary was generated for this report."}
              </p>
            </div>
            <ConfidenceExplainer confidence={report.confidence} />
          </div>
        </div>
      </div>
    </section>
  );
}

function ReportNav() {
  return (
    <nav
      aria-label="Report sections"
      className="hidden lg:sticky lg:top-24 lg:block"
    >
      <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        Contents
      </p>
      <ul className="space-y-1.5 border-l border-border">
        {NAV_SECTIONS.map((section) => (
          <li key={section.id}>
            <a
              href={`#${section.id}`}
              className="-ml-px block border-l border-transparent py-1 pl-3 text-sm text-muted-foreground transition-colors hover:border-foreground/40 hover:text-foreground"
            >
              {section.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function ReportSkeleton() {
  return (
    <div className="container max-w-6xl py-14" aria-busy="true">
      <Skeleton className="h-5 w-40" />
      <Skeleton className="mt-4 h-12 w-2/3" />
      <Skeleton className="mt-3 h-4 w-1/3" />
      <Skeleton className="mt-8 h-64 w-full" />
      <div className="mt-12 space-y-8">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    </div>
  );
}
