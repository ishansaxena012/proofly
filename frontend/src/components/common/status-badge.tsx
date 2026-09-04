import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { ClaimStatus, ResearchJobStatus, Sentiment } from "@/lib/types";
import { humanizeEnum } from "@/lib/utils";

type Variant = NonNullable<BadgeProps["variant"]>;

const JOB_STATUS_VARIANT: Record<ResearchJobStatus, Variant> = {
  CREATED: "neutral",
  QUEUED: "neutral",
  RUNNING: "outline",
  IDENTIFYING_PRODUCT: "outline",
  PLANNING_RESEARCH: "outline",
  RESEARCHING: "outline",
  EXTRACTING_EVIDENCE: "outline",
  ANALYZING: "outline",
  VERIFYING: "outline",
  GENERATING_REPORT: "outline",
  COMPLETED: "positive",
  PARTIALLY_COMPLETED: "caution",
  FAILED: "negative",
  CANCELLED: "neutral",
};

export function JobStatusBadge({ status }: { status: ResearchJobStatus }) {
  return (
    <Badge variant={JOB_STATUS_VARIANT[status] ?? "neutral"}>{humanizeEnum(status)}</Badge>
  );
}

const CLAIM_STATUS_VARIANT: Record<ClaimStatus, Variant> = {
  SUPPORTED: "positive",
  PARTIALLY_SUPPORTED: "caution",
  CONTESTED: "negative",
  INSUFFICIENT_EVIDENCE: "neutral",
};

const CLAIM_STATUS_LABEL: Record<ClaimStatus, string> = {
  SUPPORTED: "Supported",
  PARTIALLY_SUPPORTED: "Partially supported",
  CONTESTED: "Contested",
  INSUFFICIENT_EVIDENCE: "Insufficient evidence",
};

export function ClaimStatusBadge({ status }: { status: ClaimStatus }) {
  return (
    <Badge variant={CLAIM_STATUS_VARIANT[status] ?? "neutral"}>
      {CLAIM_STATUS_LABEL[status] ?? humanizeEnum(status)}
    </Badge>
  );
}

const SENTIMENT_VARIANT: Record<Sentiment, Variant> = {
  POSITIVE: "positive",
  NEGATIVE: "negative",
  MIXED: "caution",
  NEUTRAL: "neutral",
};

export function SentimentBadge({ sentiment }: { sentiment: Sentiment }) {
  return (
    <Badge variant={SENTIMENT_VARIANT[sentiment] ?? "neutral"}>
      {humanizeEnum(sentiment)}
    </Badge>
  );
}
