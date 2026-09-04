/**
 * Wire types for the Proofly public REST + SSE API.
 *
 * These mirror `docs/API.md` and `docs/ARCHITECTURE.md` exactly. Anything the
 * backend may legitimately omit or null out is typed as nullable/optional here
 * so the UI degrades honestly instead of rendering `undefined`.
 */

/* ── Job state machine (ARCHITECTURE.md §3) ─────────────────────────────── */

export const RESEARCH_JOB_STATUSES = [
  "CREATED",
  "QUEUED",
  "RUNNING",
  "IDENTIFYING_PRODUCT",
  "PLANNING_RESEARCH",
  "RESEARCHING",
  "EXTRACTING_EVIDENCE",
  "ANALYZING",
  "VERIFYING",
  "GENERATING_REPORT",
  "COMPLETED",
  "PARTIALLY_COMPLETED",
  "FAILED",
  "CANCELLED",
] as const;

export type ResearchJobStatus = (typeof RESEARCH_JOB_STATUSES)[number];

export const TERMINAL_STATUSES: ResearchJobStatus[] = [
  "COMPLETED",
  "PARTIALLY_COMPLETED",
  "FAILED",
  "CANCELLED",
];

export const REPORT_READY_STATUSES: ResearchJobStatus[] = [
  "COMPLETED",
  "PARTIALLY_COMPLETED",
];

export function isTerminalStatus(status: string | null | undefined): boolean {
  return !!status && TERMINAL_STATUSES.includes(status as ResearchJobStatus);
}

export function isReportReady(status: string | null | undefined): boolean {
  return !!status && REPORT_READY_STATUSES.includes(status as ResearchJobStatus);
}

/* ── SSE event types (API.md §Events, spec §24) ─────────────────────────── */

export const RESEARCH_EVENT_TYPES = [
  "PRODUCT_IDENTIFIED",
  "RESEARCH_STARTED",
  "WEB_RESEARCH_COMPLETED",
  "REDDIT_RESEARCH_COMPLETED",
  "YOUTUBE_RESEARCH_COMPLETED",
  "EVIDENCE_EXTRACTION_STARTED",
  "EVIDENCE_EXTRACTION_COMPLETED",
  "CLAIMS_GENERATED",
  "VERIFICATION_STARTED",
  "VERIFICATION_COMPLETED",
  "REPORT_GENERATION_STARTED",
  "REPORT_COMPLETED",
  "JOB_FAILED",
  "JOB_PARTIALLY_COMPLETED",
] as const;

export type ResearchEventType = (typeof RESEARCH_EVENT_TYPES)[number];

/** `data:` payload of an SSE frame; the `event:` name carries the type. */
export interface ResearchEventData {
  message: string | null;
  payload: Record<string, unknown> | null;
  createdAt: string;
}

export interface ResearchEvent extends ResearchEventData {
  /** Derived client-side from the SSE `event:` name. */
  eventType: ResearchEventType | string;
  /** Stable client-side key for list rendering / de-duplication. */
  key: string;
}

/* ── Domain enums ───────────────────────────────────────────────────────── */

export type SourceChannel = "WEB" | "REDDIT" | "YOUTUBE";

export type SourceType =
  | "OFFICIAL_DOC"
  | "PROFESSIONAL_REVIEW"
  | "USER_EXPERIENCE"
  | "FORUM_POST"
  | "VIDEO_REVIEW"
  | "GENERIC";

export type SourceStatus = "FETCHED" | "FAILED" | "SKIPPED";

export type Sentiment = "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "MIXED";

export type EvidenceType =
  | "FACT"
  | "SPECIFICATION"
  | "EXPERT_OPINION"
  | "CUSTOMER_EXPERIENCE"
  | "REPEATED_PATTERN"
  | "ANECDOTE"
  | "COMPARISON"
  | "MEASUREMENT"
  | "CLAIM";

export type EvidenceStrength = "STRONG" | "MODERATE" | "WEAK";

export type ClaimStatus =
  | "SUPPORTED"
  | "PARTIALLY_SUPPORTED"
  | "CONTESTED"
  | "INSUFFICIENT_EVIDENCE";

/* ── DTOs ───────────────────────────────────────────────────────────────── */

export interface Product {
  id: string;
  rawQuery: string;
  canonicalName: string | null;
  brand: string | null;
  category: string | null;
  model: string | null;
}

/** `GET /api/v1/research/{id}` */
export interface ResearchJob {
  id: string;
  status: ResearchJobStatus;
  currentStage: string | null;
  demoMode: boolean;
  product: Product | null;
  sourceCount: number;
  evidenceCount: number;
  claimCount: number;
  verifiedClaimCount: number;
  errorCode: ErrorCode | null;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

/** `POST /api/v1/research` → 202 */
export interface StartResearchResponse {
  researchJobId: string;
  status: ResearchJobStatus;
}

/** `GET /api/v1/research/{id}/sources` */
export interface ResearchSource {
  id: string;
  channel: SourceChannel;
  url: string;
  title: string | null;
  sourceType: SourceType | null;
  authorityScore: number | null;
  firstHand: boolean | null;
  independenceGroupId: string | null;
  status: SourceStatus;
}

/** `GET /api/v1/research/{id}/evidence` */
export interface Evidence {
  id: string;
  sourceId: string;
  topic: string;
  sentiment: Sentiment | null;
  evidenceType: EvidenceType;
  strength: EvidenceStrength | null;
  text: string;
}

/* ── Report DTO (API.md §Report DTO shape) ──────────────────────────────── */

export interface CategoryScore {
  category: string;
  score: number;
  confidence: number | null;
}

/** A statement backed by zero or more evidence rows. */
export interface EvidenceBackedPoint {
  text: string;
  evidenceIds: string[];
}

/** A finding traced to a single generated claim. */
export interface ClaimBackedPoint {
  text: string;
  claimId: string | null;
}

export interface ConflictPosition {
  text: string;
  evidenceIds: string[];
}

export interface ReportConflict {
  topic: string;
  positionA: ConflictPosition;
  positionB: ConflictPosition;
  explanation: string | null;
  resolved: boolean;
}

/** Evidence as embedded inside a report claim. */
export interface ClaimEvidence {
  id: string;
  text: string;
  sourceId: string | null;
}

export interface ReportClaim {
  id: string;
  topic: string;
  statement: string;
  status: ClaimStatus;
  confidence: number | null;
  supportingEvidence: ClaimEvidence[];
  contradictingEvidence: ClaimEvidence[];
}

/** Sources as embedded inside the report DTO (leaner than the sources endpoint). */
export interface ReportSource {
  id: string;
  url: string;
  title: string | null;
  sourceType: SourceType | null;
  channel: SourceChannel | null;
}

/** `GET /api/v1/research/{id}/report` */
export interface Report {
  researchJobId: string;
  demoMode: boolean;
  overallScore: number | null;
  verdict: string | null;
  confidence: number | null;
  executiveSummary: string | null;
  categoryScores: CategoryScore[];
  keyStrengths: EvidenceBackedPoint[];
  keyWeaknesses: EvidenceBackedPoint[];
  keyFindings: ClaimBackedPoint[];
  commonPraise: EvidenceBackedPoint[];
  commonComplaints: EvidenceBackedPoint[];
  conflicts: ReportConflict[];
  longTermOwnership: EvidenceBackedPoint | null;
  whoShouldBuy: string[];
  whoShouldAvoid: string[];
  caveats: string[];
  sources: ReportSource[];
  claims: ReportClaim[];
}

/** `POST /api/v1/research/{id}/followup` */
export interface FollowUpAnswer {
  answer: string;
  citedEvidenceIds: string[];
}

/* ── Errors (API.md §Error shape) ───────────────────────────────────────── */

export const ERROR_CODES = [
  "SOURCE_FAILURE",
  "AGENT_FAILURE",
  "LLM_FAILURE",
  "TIMEOUT",
  "RATE_LIMIT",
  "INVALID_PRODUCT",
  "INSUFFICIENT_DATA",
  "NOT_FOUND",
  "VALIDATION_ERROR",
  "UNAUTHORIZED",
  "FORBIDDEN",
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

export interface ApiErrorBody {
  errorCode: ErrorCode | string;
  message: string;
  timestamp: string;
}

/** `409` body returned by the report endpoint before the job is finished. */
export interface ReportNotReadyBody {
  status: ResearchJobStatus;
}
