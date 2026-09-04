"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";

import { ConfidenceMeter } from "@/components/common/measures";
import { ClaimStatusBadge } from "@/components/common/status-badge";
import { EvidenceCard } from "@/components/report/evidence-disclosure";
import { useReportData } from "@/components/report/report-context";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import type { ClaimEvidence, ReportClaim } from "@/lib/types";
import { cn } from "@/lib/utils";

function EvidenceGroup({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "support" | "contradict";
  items: ClaimEvidence[];
}) {
  const { evidenceById, sourceById } = useReportData();
  if (items.length === 0) return null;

  return (
    <div>
      <h4
        className={cn(
          "mb-2 text-xs font-medium uppercase tracking-[0.14em]",
          tone === "support" ? "text-positive" : "text-negative",
        )}
      >
        {title}
        <span className="ml-1.5 font-mono normal-case tracking-normal opacity-70">
          ({items.length})
        </span>
      </h4>
      <ul className="space-y-2">
        {items.map((item) => {
          const record = evidenceById.get(item.id) ?? {
            id: item.id,
            text: item.text,
            sourceId: item.sourceId ?? null,
            topic: null,
            sentiment: null,
            evidenceType: null,
            strength: null,
          };
          return (
            <EvidenceCard
              key={item.id}
              evidence={record}
              source={record.sourceId ? sourceById.get(record.sourceId) : undefined}
              className={
                tone === "support"
                  ? "border-l-2 border-l-positive/50"
                  : "border-l-2 border-l-negative/50"
              }
            />
          );
        })}
      </ul>
    </div>
  );
}

/** Full detail of a single claim: status, confidence, and both sides of its evidence. */
export function ClaimDetail({ claim }: { claim: ReportClaim }) {
  const supporting = claim.supportingEvidence ?? [];
  const contradicting = claim.contradictingEvidence ?? [];
  const total = supporting.length + contradicting.length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <ClaimStatusBadge status={claim.status} />
        {claim.topic ? <Badge variant="outline">{claim.topic}</Badge> : null}
        {contradicting.length > 0 ? (
          <Badge variant="caution">Contradicted by {contradicting.length}</Badge>
        ) : null}
      </div>

      <ConfidenceMeter
        confidence={claim.confidence}
        label="Claim confidence"
        className="max-w-xs"
      />

      {total === 0 ? (
        <p className="rounded-md border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
          No evidence rows were returned for this claim, which is why it is marked{" "}
          {claim.status.replace(/_/g, " ").toLowerCase()}.
        </p>
      ) : (
        <div className="space-y-5">
          <EvidenceGroup title="Supporting evidence" tone="support" items={supporting} />
          <EvidenceGroup
            title="Contradicting evidence"
            tone="contradict"
            items={contradicting}
          />
        </div>
      )}
    </div>
  );
}

/** A key finding that opens into the claim — and then the evidence — behind it. */
export function FindingDisclosure({
  text,
  claimId,
}: {
  text: string;
  claimId: string | null;
}) {
  const { claimById } = useReportData();
  const [open, setOpen] = React.useState(false);
  const contentId = React.useId();
  const claim = claimId ? claimById.get(claimId) : undefined;

  return (
    <li className="border-t border-border py-4 first:border-t-0 first:pt-0">
      <div className="flex items-start gap-3">
        <p className="min-w-0 flex-1 text-sm leading-6">{text}</p>
        {claim ? (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-controls={contentId}
            className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-full border border-border px-2.5 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Trace claim
            <span className="sr-only">{open ? "— hide" : "— show"} the underlying claim</span>
            <ChevronDown
              aria-hidden="true"
              className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
            />
          </button>
        ) : (
          <span className="mt-0.5 shrink-0 rounded-full border border-dashed border-border px-2.5 py-1 text-[11px] text-muted-foreground/70">
            No claim linked
          </span>
        )}
      </div>

      {claim && open ? (
        <div id={contentId} className="mt-4 animate-fade-in rounded-md bg-muted/50 p-4">
          <p className="mb-3 text-sm font-medium">{claim.statement}</p>
          <ClaimDetail claim={claim} />
        </div>
      ) : (
        <div id={contentId} hidden />
      )}
    </li>
  );
}

/** Every generated claim, expandable. The audit trail for the whole report. */
export function ClaimLedger({ claims }: { claims: ReportClaim[] }) {
  return (
    <Accordion type="multiple" className="rounded-lg border border-border bg-card px-4">
      {claims.map((claim) => (
        <AccordionItem key={claim.id} value={claim.id}>
          <AccordionTrigger>
            <span className="flex min-w-0 flex-col gap-2 pr-2">
              <span className="flex flex-wrap items-center gap-2">
                <ClaimStatusBadge status={claim.status} />
                {claim.topic ? (
                  <span className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                    {claim.topic}
                  </span>
                ) : null}
              </span>
              <span className="text-sm font-medium leading-6">{claim.statement}</span>
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <ClaimDetail claim={claim} />
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
