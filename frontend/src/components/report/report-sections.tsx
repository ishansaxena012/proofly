"use client";

import * as React from "react";
import { CircleAlert, Minus, Plus, ThumbsDown, ThumbsUp, Unlink } from "lucide-react";

import { ConfidenceMeter, confidenceLabel } from "@/components/common/measures";
import { EmptyState } from "@/components/common/states";
import { EvidenceDisclosure } from "@/components/report/evidence-disclosure";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type {
  CategoryScore,
  EvidenceBackedPoint,
  ReportConflict,
} from "@/lib/types";
import { cn, formatConfidence } from "@/lib/utils";

/* ── Section shell ──────────────────────────────────────────────────────── */

export function ReportSection({
  id,
  title,
  description,
  aside,
  children,
  className,
}: {
  id: string;
  title: string;
  description?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={cn("scroll-mt-24 border-t border-border pt-10", className)}>
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="display text-2xl font-semibold sm:text-[1.75rem]">{title}</h2>
          {description ? (
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

/* ── Category scores ────────────────────────────────────────────────────── */

export function CategoryScores({ items }: { items: CategoryScore[] }) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No category scores"
        description="The evidence gathered was not sufficient to score individual categories for this product."
      />
    );
  }

  return (
    <ul className="grid gap-x-10 gap-y-6 sm:grid-cols-2">
      {items.map((item) => {
        const score = Math.max(0, Math.min(100, item.score ?? 0));
        const tone =
          score >= 75 ? "bg-positive" : score >= 55 ? "bg-caution" : "bg-negative";
        return (
          <li key={item.category}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm font-medium">{item.category}</span>
              <span className="display text-lg font-semibold tabular-nums">
                {Math.round(score)}
              </span>
            </div>
            <div
              role="meter"
              aria-valuenow={Math.round(score)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${item.category}: ${Math.round(score)} out of 100, ${confidenceLabel(item.confidence).toLowerCase()}`}
              className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted"
            >
              <div className={cn("h-full rounded-full", tone)} style={{ width: `${score}%` }} />
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {confidenceLabel(item.confidence)} · {formatConfidence(item.confidence)}
            </p>
          </li>
        );
      })}
    </ul>
  );
}

/* ── Evidence-backed point lists ────────────────────────────────────────── */

const POINT_TONE = {
  positive: {
    icon: Plus,
    className: "text-positive",
    empty: "No strengths were supported by enough evidence to state.",
  },
  negative: {
    icon: Minus,
    className: "text-negative",
    empty: "No weaknesses were supported by enough evidence to state.",
  },
  praise: {
    icon: ThumbsUp,
    className: "text-positive",
    empty: "No repeated praise emerged across the sources gathered.",
  },
  complaint: {
    icon: ThumbsDown,
    className: "text-negative",
    empty: "No repeated complaints emerged across the sources gathered.",
  },
  neutral: {
    icon: CircleAlert,
    className: "text-muted-foreground",
    empty: "Nothing was reported for this section.",
  },
} as const;

export function PointList({
  points,
  tone = "neutral",
  label,
}: {
  points: EvidenceBackedPoint[];
  tone?: keyof typeof POINT_TONE;
  /** Used for the accessible name of each disclosure control. */
  label?: string;
}) {
  const config = POINT_TONE[tone];
  const Icon = config.icon;

  if (points.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
        {config.empty}
      </p>
    );
  }

  return (
    <ul className="divide-y divide-border">
      {points.map((point, index) => (
        <li key={`${point.text}-${index}`} className="py-4 first:pt-0 last:pb-0">
          <EvidenceDisclosure
            evidenceIds={point.evidenceIds ?? []}
            label={label ? `${label}: ${point.text.slice(0, 60)}` : undefined}
          >
            <span className="flex gap-2.5">
              <Icon
                aria-hidden="true"
                className={cn("mt-1 h-4 w-4 shrink-0", config.className)}
              />
              <span>{point.text}</span>
            </span>
          </EvidenceDisclosure>
        </li>
      ))}
    </ul>
  );
}

/* ── Conflicts ──────────────────────────────────────────────────────────── */

/**
 * Conflicting evidence is the section the whole product exists for: both
 * positions are shown at equal weight, side by side, each with its own
 * evidence, and an unresolved conflict is labelled as unresolved rather than
 * blended into a single number or sentence.
 */
export function ConflictList({ conflicts }: { conflicts: ReportConflict[] }) {
  if (conflicts.length === 0) {
    return (
      <EmptyState
        icon={<Unlink className="h-6 w-6" />}
        title="No conflicting evidence was found"
        description="The sources gathered did not contradict each other on any topic covered by this report. That is not the same as universal agreement — it reflects only what was gathered."
      />
    );
  }

  return (
    <div className="space-y-6">
      {conflicts.map((conflict, index) => (
        <Card key={`${conflict.topic}-${index}`} className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/50 px-6 py-4">
            <h3 className="text-base font-semibold">{conflict.topic}</h3>
            {conflict.resolved ? (
              <Badge variant="secondary">Resolved by context</Badge>
            ) : (
              <Badge variant="caution">Unresolved disagreement</Badge>
            )}
          </div>

          <CardContent className="p-0">
            <div className="grid divide-y divide-border md:grid-cols-2 md:divide-x md:divide-y-0">
              <ConflictPositionBlock
                marker="Position A"
                text={conflict.positionA?.text ?? ""}
                evidenceIds={conflict.positionA?.evidenceIds ?? []}
                topic={conflict.topic}
              />
              <ConflictPositionBlock
                marker="Position B"
                text={conflict.positionB?.text ?? ""}
                evidenceIds={conflict.positionB?.evidenceIds ?? []}
                topic={conflict.topic}
              />
            </div>

            <div className="border-t border-border bg-background px-6 py-4">
              <h4 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                Why the sources disagree
              </h4>
              <p className="mt-2 text-sm leading-6">
                {conflict.explanation ??
                  "No explanation was produced for this disagreement. The two positions are presented as they were found."}
              </p>
              {!conflict.resolved ? (
                <p className="mt-3 text-xs text-caution">
                  This disagreement has not been resolved. Neither position has been
                  discarded, and the overall score reflects the uncertainty rather than
                  averaging the two.
                </p>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ConflictPositionBlock({
  marker,
  text,
  evidenceIds,
  topic,
}: {
  marker: string;
  text: string;
  evidenceIds: string[];
  topic: string;
}) {
  return (
    <div className="px-6 py-5">
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
        {marker}
      </p>
      <EvidenceDisclosure evidenceIds={evidenceIds} label={`${topic}, ${marker}`}>
        <span className="font-medium">{text || "No statement was recorded."}</span>
      </EvidenceDisclosure>
    </div>
  );
}

/* ── Audience + caveats ─────────────────────────────────────────────────── */

export function AudienceList({
  items,
  tone,
  emptyMessage,
}: {
  items: string[];
  tone: "buy" | "avoid";
  emptyMessage: string;
}) {
  if (items.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
        {emptyMessage}
      </p>
    );
  }

  const Icon = tone === "buy" ? ThumbsUp : ThumbsDown;

  return (
    <ul className="space-y-3">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="flex gap-2.5 text-sm leading-6">
          <Icon
            aria-hidden="true"
            className={cn(
              "mt-1 h-4 w-4 shrink-0",
              tone === "buy" ? "text-positive" : "text-negative",
            )}
          />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function CaveatList({ caveats }: { caveats: string[] }) {
  if (caveats.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
        No limitations were recorded for this run. That does not mean there were none —
        check the sources and confidence values before relying on any single claim.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {caveats.map((caveat, index) => (
        <li
          key={`${caveat}-${index}`}
          className="flex gap-2.5 rounded-md border border-caution/30 bg-caution/5 px-4 py-3 text-sm leading-6 text-foreground"
        >
          <CircleAlert aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-caution" />
          <span>{caveat}</span>
        </li>
      ))}
    </ul>
  );
}

/* ── Verdict summary strip ──────────────────────────────────────────────── */

export function ConfidenceExplainer({ confidence }: { confidence: number | null }) {
  return (
    <div className="rounded-md border border-border bg-muted/40 p-4">
      <ConfidenceMeter confidence={confidence} label="Report confidence" />
      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        Confidence measures the evidence, not the model. It rises with independent,
        first-hand, mutually-corroborating sources and falls with thin, duplicated or
        derivative ones. A low value here means the report is honest about what it could
        not establish.
      </p>
    </div>
  );
}
