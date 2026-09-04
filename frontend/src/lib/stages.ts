/**
 * Maps the real pipeline (`Sources → Evidence → Claims → Verification →
 * Report`) onto the SSE event stream + job state machine.
 *
 * There is deliberately no synthetic percentage anywhere in here: a stage is
 * pending, running, done, degraded (a channel that produced nothing) or failed,
 * and every one of those states is derived from something the backend actually
 * reported.
 */

import type { ResearchEvent, ResearchEventType, ResearchJobStatus } from "@/lib/types";

export type StageState = "pending" | "running" | "done" | "degraded" | "failed";

export interface PipelineStageDefinition {
  id: string;
  title: string;
  /** What the stage actually does, in the product's own vocabulary. */
  description: string;
  startEvent?: ResearchEventType;
  completeEvent: ResearchEventType;
  /** Job statuses during which this stage is the one currently running. */
  activeStatuses: ResearchJobStatus[];
  /** Statuses at or beyond which the stage should already have completed. */
  completedByOrdinal: number;
  /**
   * Channel research degrades gracefully — a channel that never reported a
   * completion event is shown as "no results", not as a hard failure.
   */
  degradable?: boolean;
}

/** Position of each status along the happy path. Terminal failures are -1. */
const STATUS_ORDINAL: Record<ResearchJobStatus, number> = {
  CREATED: 0,
  QUEUED: 1,
  RUNNING: 2,
  IDENTIFYING_PRODUCT: 3,
  PLANNING_RESEARCH: 4,
  RESEARCHING: 5,
  EXTRACTING_EVIDENCE: 6,
  ANALYZING: 7,
  VERIFYING: 8,
  GENERATING_REPORT: 9,
  COMPLETED: 10,
  PARTIALLY_COMPLETED: 10,
  FAILED: -1,
  CANCELLED: -1,
};

export function statusOrdinal(status: ResearchJobStatus | null | undefined): number {
  if (!status) return 0;
  return STATUS_ORDINAL[status] ?? 0;
}

export const PIPELINE_STAGES: PipelineStageDefinition[] = [
  {
    id: "product",
    title: "Product identified",
    description:
      "Resolves the query to one canonical product — brand, model, category — so every later step researches the same thing.",
    completeEvent: "PRODUCT_IDENTIFIED",
    activeStatuses: ["CREATED", "QUEUED", "RUNNING", "IDENTIFYING_PRODUCT"],
    completedByOrdinal: 4,
  },
  {
    id: "plan",
    title: "Research plan",
    description:
      "Chooses the dimensions worth investigating for this category and the queries to run on each channel.",
    completeEvent: "RESEARCH_STARTED",
    activeStatuses: ["PLANNING_RESEARCH"],
    completedByOrdinal: 5,
  },
  {
    id: "web",
    title: "Web research",
    description:
      "Professional reviews, official documentation and editorial coverage. Collected as sources, not answers.",
    completeEvent: "WEB_RESEARCH_COMPLETED",
    activeStatuses: ["RESEARCHING"],
    completedByOrdinal: 6,
    degradable: true,
  },
  {
    id: "reddit",
    title: "Reddit research",
    description:
      "First-hand owner reports and long-term threads — the complaints that only surface after months of use.",
    completeEvent: "REDDIT_RESEARCH_COMPLETED",
    activeStatuses: ["RESEARCHING"],
    completedByOrdinal: 6,
    degradable: true,
  },
  {
    id: "youtube",
    title: "YouTube research",
    description:
      "Video reviews and measurement-heavy channels, read through transcripts rather than thumbnails.",
    completeEvent: "YOUTUBE_RESEARCH_COMPLETED",
    activeStatuses: ["RESEARCHING"],
    completedByOrdinal: 6,
    degradable: true,
  },
  {
    id: "evidence",
    title: "Evidence extraction",
    description:
      "Splits every fetched document into passages and pulls out typed, attributed evidence — each one traceable to its source.",
    startEvent: "EVIDENCE_EXTRACTION_STARTED",
    completeEvent: "EVIDENCE_EXTRACTION_COMPLETED",
    activeStatuses: ["EXTRACTING_EVIDENCE"],
    completedByOrdinal: 7,
  },
  {
    id: "claims",
    title: "Claims generated",
    description:
      "Groups evidence into candidate claims per topic, keeping agreeing and disagreeing evidence attached to the same claim.",
    completeEvent: "CLAIMS_GENERATED",
    activeStatuses: ["ANALYZING"],
    completedByOrdinal: 8,
  },
  {
    id: "verification",
    title: "Verification",
    description:
      "Checks each claim against its evidence, scores confidence from evidence quality and independence, and preserves conflicts instead of averaging them.",
    startEvent: "VERIFICATION_STARTED",
    completeEvent: "VERIFICATION_COMPLETED",
    activeStatuses: ["VERIFYING"],
    completedByOrdinal: 9,
  },
  {
    id: "report",
    title: "Report generation",
    description:
      "Assembles the final report. The overall score is derived from verified claims — it is never invented by the model.",
    startEvent: "REPORT_GENERATION_STARTED",
    completeEvent: "REPORT_COMPLETED",
    activeStatuses: ["GENERATING_REPORT"],
    completedByOrdinal: 10,
  },
];

export interface ResolvedStage extends PipelineStageDefinition {
  state: StageState;
  /** The event that completed (or started) this stage, when we have it. */
  event: ResearchEvent | null;
  detail: string | null;
}

export function resolveStages(
  status: ResearchJobStatus | null | undefined,
  events: ResearchEvent[],
): ResolvedStage[] {
  const byType = new Map<string, ResearchEvent>();
  for (const event of events) {
    // Keep the first occurrence of each type: replayed history is chronological.
    if (!byType.has(event.eventType)) byType.set(event.eventType, event);
  }

  const ordinal = statusOrdinal(status);
  const failed = status === "FAILED" || status === "CANCELLED";
  const jobFailedEvent = byType.get("JOB_FAILED") ?? null;

  // How far the job actually got, for FAILED jobs where the status ordinal is -1.
  const reachedOrdinal = failed
    ? PIPELINE_STAGES.reduce(
        (max, stage) =>
          byType.has(stage.completeEvent) ? Math.max(max, stage.completedByOrdinal) : max,
        0,
      )
    : ordinal;

  return PIPELINE_STAGES.map((stage) => {
    const completeEvent = byType.get(stage.completeEvent) ?? null;
    const startEvent = stage.startEvent ? (byType.get(stage.startEvent) ?? null) : null;

    let state: StageState;
    let event: ResearchEvent | null = completeEvent;
    let detail: string | null = null;

    if (completeEvent) {
      state = "done";
      detail = completeEvent.message;
    } else if (failed) {
      if (reachedOrdinal >= stage.completedByOrdinal) {
        // The job moved past this stage before dying, but never emitted its event.
        state = stage.degradable ? "degraded" : "pending";
        detail = stage.degradable ? "No results reported for this channel." : null;
      } else if (
        reachedOrdinal + 1 >= stage.completedByOrdinal ||
        Boolean(startEvent)
      ) {
        state = "failed";
        event = jobFailedEvent ?? startEvent;
        detail = jobFailedEvent?.message ?? "This stage did not complete.";
      } else {
        state = "pending";
        detail = "Not reached.";
      }
    } else if (ordinal >= stage.completedByOrdinal) {
      // The job is past this stage but never reported completion.
      state = stage.degradable ? "degraded" : "done";
      detail = stage.degradable ? "No results reported for this channel." : null;
    } else if (startEvent || (status && stage.activeStatuses.includes(status))) {
      state = "running";
      event = startEvent;
      detail = startEvent?.message ?? null;
    } else {
      state = "pending";
    }

    return { ...stage, state, event, detail };
  });
}

/** Short, non-numeric summary of where the job is right now. */
export function currentStageLabel(stages: ResolvedStage[]): string | null {
  const running = stages.find((s) => s.state === "running");
  if (running) return running.title;
  const failedStage = stages.find((s) => s.state === "failed");
  if (failedStage) return failedStage.title;
  return null;
}

const EVENT_LABELS: Record<ResearchEventType, string> = {
  PRODUCT_IDENTIFIED: "Product identified",
  RESEARCH_STARTED: "Research started",
  WEB_RESEARCH_COMPLETED: "Web research completed",
  REDDIT_RESEARCH_COMPLETED: "Reddit research completed",
  YOUTUBE_RESEARCH_COMPLETED: "YouTube research completed",
  EVIDENCE_EXTRACTION_STARTED: "Evidence extraction started",
  EVIDENCE_EXTRACTION_COMPLETED: "Evidence extraction completed",
  CLAIMS_GENERATED: "Claims generated",
  VERIFICATION_STARTED: "Verification started",
  VERIFICATION_COMPLETED: "Verification completed",
  REPORT_GENERATION_STARTED: "Report generation started",
  REPORT_COMPLETED: "Report completed",
  JOB_FAILED: "Job failed",
  JOB_PARTIALLY_COMPLETED: "Job partially completed",
};

export function eventLabel(eventType: string): string {
  return (
    EVENT_LABELS[eventType as ResearchEventType] ??
    eventType.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase())
  );
}
