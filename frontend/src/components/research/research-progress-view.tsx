"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, CircleSlash, FileText, TriangleAlert } from "lucide-react";

import { DemoModeBanner, DemoModeBadge } from "@/components/common/demo-mode-banner";
import { EmptyState, ErrorState } from "@/components/common/states";
import { JobStatusBadge } from "@/components/common/status-badge";
import { EventLog, EventStreamIndicator } from "@/components/research/event-log";
import { PipelineTimeline } from "@/components/research/pipeline-timeline";
import { SourcesPanel } from "@/components/research/sources-panel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useResearchEvents } from "@/lib/hooks/use-research-events";
import { useResearchJob, useSources } from "@/lib/queries";
import { currentStageLabel, resolveStages } from "@/lib/stages";
import { isReportReady, isTerminalStatus, type ResearchJob } from "@/lib/types";
import { formatElapsed, formatTimestamp, humanizeEnum } from "@/lib/utils";

export function ResearchProgressView({ researchJobId }: { researchJobId: string }) {
  const jobQuery = useResearchJob(researchJobId);
  const job = jobQuery.data;

  const { events, status: streamStatus, transport } = useResearchEvents(researchJobId);

  const stages = React.useMemo(
    () => resolveStages(job?.status ?? null, events),
    [job?.status, events],
  );

  const sourcesQuery = useSources(researchJobId, {
    enabled: Boolean(job && job.sourceCount > 0),
  });

  if (jobQuery.isLoading) return <ProgressSkeleton />;

  if (jobQuery.isError) {
    return (
      <div className="container max-w-4xl py-14">
        <ErrorState
          context="research job"
          error={jobQuery.error}
          onRetry={() => void jobQuery.refetch()}
        />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="container max-w-4xl py-14">
        <EmptyState
          title="No job data"
          description="The backend returned an empty response for this research job."
        />
      </div>
    );
  }

  const terminal = isTerminalStatus(job.status);
  const reportReady = isReportReady(job.status);
  const running = currentStageLabel(stages);
  const productName =
    job.product?.canonicalName || job.product?.rawQuery || "Unidentified product";

  return (
    <div className="container max-w-4xl py-10 sm:py-14">
      <header className="mb-8">
        <div className="flex flex-wrap items-center gap-2">
          <JobStatusBadge status={job.status} />
          {job.demoMode ? <DemoModeBadge /> : null}
          <span className="ml-auto font-mono text-xs text-muted-foreground">
            {job.id}
          </span>
        </div>

        <h1 className="display mt-4 text-3xl font-semibold sm:text-4xl">{productName}</h1>

        {job.product ? (
          <p className="mt-2 text-sm text-muted-foreground">
            {[job.product.brand, job.product.model, job.product.category]
              .filter(Boolean)
              .join(" · ") || "Resolving product details…"}
            {job.product.canonicalName && job.product.rawQuery !== job.product.canonicalName ? (
              <>
                {" "}
                <span className="opacity-70">
                  (from &ldquo;{job.product.rawQuery}&rdquo;)
                </span>
              </>
            ) : null}
          </p>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            The product has not been resolved yet.
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
          <EventStreamIndicator status={streamStatus} transport={transport} />
          <span>Started {formatTimestamp(job.startedAt ?? job.createdAt)}</span>
          <span>
            {terminal ? "Ran for" : "Running for"}{" "}
            {formatElapsed(job.startedAt ?? job.createdAt, job.completedAt)}
          </span>
          {!terminal && running ? (
            <span className="text-foreground">Now: {running}</span>
          ) : null}
          {job.currentStage && !terminal ? (
            <span className="font-mono">{humanizeEnum(job.currentStage)}</span>
          ) : null}
        </div>
      </header>

      {job.demoMode ? <DemoModeBanner className="mb-6" /> : null}

      <TerminalNotice job={job} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_240px] lg:items-start">
        <Card className="order-2 lg:order-1">
          <CardHeader>
            <CardTitle>Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <PipelineTimeline stages={stages} />
          </CardContent>
        </Card>

        <Card className="order-1 lg:order-2 lg:sticky lg:top-24">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Collected so far
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4 lg:grid-cols-1">
              <Counter label="Sources" value={job.sourceCount} />
              <Counter label="Evidence" value={job.evidenceCount} />
              <Counter label="Claims" value={job.claimCount} />
              <Counter
                label="Verified claims"
                value={job.verifiedClaimCount}
                hint={
                  job.claimCount > 0
                    ? `of ${job.claimCount}`
                    : undefined
                }
              />
            </dl>
          </CardContent>
        </Card>
      </div>

      <section className="mt-8 space-y-4">
        <EventLog events={events} />
      </section>

      {job.sourceCount > 0 ? (
        <section className="mt-10">
          <h2 className="display mb-4 text-xl font-semibold">Sources gathered</h2>
          {sourcesQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : sourcesQuery.isError ? (
            <ErrorState
              context="sources"
              error={sourcesQuery.error}
              onRetry={() => void sourcesQuery.refetch()}
            />
          ) : (
            <SourcesPanel sources={sourcesQuery.data ?? []} />
          )}
        </section>
      ) : null}

      {reportReady ? (
        <div className="mt-10 flex justify-center">
          <Button size="lg" asChild>
            <Link href={`/research/${job.id}/report`}>
              <FileText aria-hidden="true" />
              Open the report
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function Counter({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">{label}</dt>
      <dd className="mt-1 flex items-baseline gap-1.5">
        <span className="display text-2xl font-semibold tabular-nums">{value}</span>
        {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
      </dd>
    </div>
  );
}

/** Honest messaging for every terminal state. */
function TerminalNotice({ job }: { job: ResearchJob }) {
  if (job.status === "COMPLETED") {
    return (
      <Alert variant="info" className="mb-6">
        <FileText aria-hidden="true" />
        <AlertTitle>Research complete</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            All stages finished. The report is built from {job.verifiedClaimCount} verified
            claim{job.verifiedClaimCount === 1 ? "" : "s"} across {job.sourceCount} source
            {job.sourceCount === 1 ? "" : "s"}.
          </p>
          <Button size="sm" asChild>
            <Link href={`/research/${job.id}/report`}>
              Open the report
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (job.status === "PARTIALLY_COMPLETED") {
    return (
      <Alert variant="warning" className="mb-6">
        <TriangleAlert aria-hidden="true" />
        <AlertTitle>Partially completed — read the caveats</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            Part of the pipeline degraded, so this report rests on less evidence than a full
            run. It has still been produced from the evidence that was gathered, and the
            report lists exactly what was missing.
          </p>
          {job.errorMessage ? (
            <p className="text-sm">
              <span className="font-medium">Reported reason:</span> {job.errorMessage}
              {job.errorCode ? (
                <span className="ml-2 font-mono text-xs opacity-80">({job.errorCode})</span>
              ) : null}
            </p>
          ) : null}
          <Button size="sm" variant="outline" asChild>
            <Link href={`/research/${job.id}/report`}>
              Open the partial report
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (job.status === "FAILED") {
    return (
      <Alert variant="destructive" className="mb-6">
        <TriangleAlert aria-hidden="true" />
        <AlertTitle>This research job failed</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            The pipeline stopped before it could produce a report, so there is nothing to
            show. No partial answer is generated from incomplete evidence.
          </p>
          {job.errorMessage || job.errorCode ? (
            <p className="text-sm">
              {job.errorMessage ?? "No further detail was reported."}
              {job.errorCode ? (
                <span className="ml-2 font-mono text-xs opacity-80">({job.errorCode})</span>
              ) : null}
            </p>
          ) : null}
          <Button size="sm" variant="outline" asChild>
            <Link href="/research">Start a new job</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (job.status === "CANCELLED") {
    return (
      <Alert className="mb-6">
        <CircleSlash aria-hidden="true" />
        <AlertTitle>This job was cancelled</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            The run was stopped before completion. Anything already collected is listed
            below, but no report was generated.
          </p>
          <Button size="sm" variant="outline" asChild>
            <Link href="/research">Start a new job</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return null;
}

function ProgressSkeleton() {
  return (
    <div className="container max-w-4xl py-14" aria-busy="true">
      <Skeleton className="h-6 w-32" />
      <Skeleton className="mt-4 h-10 w-2/3" />
      <Skeleton className="mt-3 h-4 w-1/2" />
      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_240px]">
        <Skeleton className="h-[28rem] w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    </div>
  );
}
