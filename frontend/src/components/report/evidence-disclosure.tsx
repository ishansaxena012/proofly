"use client";

import * as React from "react";
import { ChevronDown, ExternalLink, FileWarning } from "lucide-react";

import { SentimentBadge } from "@/components/common/status-badge";
import {
  useReportData,
  type EvidenceRecord,
  type SourceRecord,
} from "@/components/report/report-context";
import { ChannelIcon } from "@/components/research/sources-panel";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { SourceChannel } from "@/lib/types";
import { cn, hostnameOf, humanizeEnum } from "@/lib/utils";

const STRENGTH_VARIANT = {
  STRONG: "positive",
  MODERATE: "caution",
  WEAK: "neutral",
} as const;

/** The passage/source layer: one piece of evidence, quoted, with its origin. */
export function EvidenceCard({
  evidence,
  source,
  className,
}: {
  evidence: EvidenceRecord;
  source: SourceRecord | undefined;
  className?: string;
}) {
  return (
    <li
      className={cn(
        "rounded-md border border-border bg-background p-3.5 text-sm",
        className,
      )}
    >
      <blockquote className="border-l-2 border-border pl-3 italic leading-6 text-foreground/90">
        &ldquo;{evidence.text}&rdquo;
      </blockquote>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        {evidence.evidenceType ? (
          <Badge variant="secondary">{humanizeEnum(evidence.evidenceType)}</Badge>
        ) : null}
        {evidence.strength ? (
          <Badge variant={STRENGTH_VARIANT[evidence.strength] ?? "neutral"}>
            {humanizeEnum(evidence.strength)} evidence
          </Badge>
        ) : null}
        {evidence.sentiment ? <SentimentBadge sentiment={evidence.sentiment} /> : null}
        {evidence.topic ? <Badge variant="outline">{evidence.topic}</Badge> : null}
      </div>

      <div className="mt-2.5 border-t border-dashed border-border pt-2.5">
        {source ? (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-start gap-2 rounded-sm text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            <ChannelIcon
              channel={(source.channel as SourceChannel | null) ?? null}
              className="mt-0.5 h-3.5 w-3.5 shrink-0"
            />
            <span className="break-words">
              {source.title || hostnameOf(source.url)}
              <span className="ml-1.5 font-mono opacity-70">
                {hostnameOf(source.url)}
              </span>
            </span>
            <ExternalLink aria-hidden="true" className="mt-0.5 h-3 w-3 shrink-0" />
            <span className="sr-only">(opens the original source in a new tab)</span>
          </a>
        ) : (
          <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <FileWarning aria-hidden="true" className="h-3.5 w-3.5" />
            Source record not included in this response
            {evidence.sourceId ? (
              <span className="font-mono opacity-70">({evidence.sourceId})</span>
            ) : null}
          </p>
        )}
      </div>
    </li>
  );
}

/** Resolves ids through the report index and renders the cards. */
export function EvidenceCardList({ evidenceIds }: { evidenceIds: string[] }) {
  const { evidenceById, sourceById, evidenceLoading } = useReportData();

  if (evidenceIds.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
        No evidence was attached to this point. Treat it as unsupported.
      </p>
    );
  }

  const resolved = evidenceIds
    .map((id) => evidenceById.get(id))
    .filter((item): item is EvidenceRecord => Boolean(item));

  if (resolved.length === 0 && evidenceLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  const missing = evidenceIds.length - resolved.length;

  return (
    <div className="space-y-2">
      <ul className="space-y-2">
        {resolved.map((evidence) => (
          <EvidenceCard
            key={evidence.id}
            evidence={evidence}
            source={evidence.sourceId ? sourceById.get(evidence.sourceId) : undefined}
          />
        ))}
      </ul>
      {missing > 0 ? (
        <p className="text-xs text-muted-foreground">
          {missing} referenced evidence record{missing === 1 ? "" : "s"} could not be
          retrieved from the API. Nothing has been substituted in their place.
        </p>
      ) : null}
    </div>
  );
}

/**
 * The progressive-disclosure control used throughout the report:
 * a statement that opens into the evidence behind it.
 *
 * Implemented as a native `<button aria-expanded aria-controls>` + region so it
 * is keyboard-operable and announced correctly.
 */
export function EvidenceDisclosure({
  evidenceIds,
  children,
  label,
  className,
  defaultOpen = false,
}: {
  evidenceIds: string[];
  /** The statement itself. */
  children: React.ReactNode;
  /** Accessible name suffix, e.g. the topic. */
  label?: string;
  className?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  const contentId = React.useId();
  const count = evidenceIds.length;

  return (
    <div className={cn("group", className)}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1 text-sm leading-6">{children}</div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls={contentId}
          className={cn(
            "mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            count > 0
              ? "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground"
              : "border-dashed border-border text-muted-foreground/70",
          )}
        >
          {count} evidence
          <span className="sr-only">
            {open ? "— hide" : "— show"} supporting evidence
            {label ? ` for ${label}` : ""}
          </span>
          <ChevronDown
            aria-hidden="true"
            className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
          />
        </button>
      </div>

      {open ? (
        <div id={contentId} className="mt-3 animate-fade-in">
          <EvidenceCardList evidenceIds={evidenceIds} />
        </div>
      ) : (
        <div id={contentId} hidden />
      )}
    </div>
  );
}
