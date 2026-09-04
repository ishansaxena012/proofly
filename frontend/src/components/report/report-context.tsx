"use client";

import * as React from "react";

import type {
  Evidence,
  EvidenceStrength,
  EvidenceType,
  Report,
  ReportClaim,
  ReportSource,
  ResearchSource,
  Sentiment,
} from "@/lib/types";

/**
 * Unified evidence record.
 *
 * The report DTO embeds a lean form of evidence inside each claim
 * (`{id, text, sourceId}`), while `GET /research/{id}/evidence` returns the full
 * row (topic, sentiment, type, strength). Both are merged so any evidence id
 * mentioned anywhere in the report can be opened, with as much detail as the
 * backend actually provided.
 */
export interface EvidenceRecord {
  id: string;
  text: string;
  sourceId: string | null;
  topic: string | null;
  sentiment: Sentiment | null;
  evidenceType: EvidenceType | null;
  strength: EvidenceStrength | null;
}

/** Sources may come from the report DTO or the richer sources endpoint. */
export interface SourceRecord {
  id: string;
  url: string;
  title: string | null;
  sourceType: string | null;
  channel: string | null;
  authorityScore: number | null;
  firstHand: boolean | null;
  independenceGroupId: string | null;
  status: string | null;
}

interface ReportDataValue {
  report: Report;
  evidenceById: Map<string, EvidenceRecord>;
  sourceById: Map<string, SourceRecord>;
  claimById: Map<string, ReportClaim>;
  /** True while the full evidence endpoint is still loading. */
  evidenceLoading: boolean;
}

const ReportDataContext = React.createContext<ReportDataValue | null>(null);

export function useReportData(): ReportDataValue {
  const context = React.useContext(ReportDataContext);
  if (!context) throw new Error("useReportData must be used inside <ReportDataProvider>.");
  return context;
}

export function ReportDataProvider({
  report,
  evidence,
  sources,
  evidenceLoading,
  children,
}: {
  report: Report;
  evidence: Evidence[] | undefined;
  sources: ResearchSource[] | undefined;
  evidenceLoading: boolean;
  children: React.ReactNode;
}) {
  const value = React.useMemo<ReportDataValue>(() => {
    const evidenceById = new Map<string, EvidenceRecord>();

    // Start from the lean copies embedded in claims so nothing is unresolvable
    // even when the evidence endpoint is unavailable.
    for (const claim of report.claims ?? []) {
      for (const item of [
        ...(claim.supportingEvidence ?? []),
        ...(claim.contradictingEvidence ?? []),
      ]) {
        if (!evidenceById.has(item.id)) {
          evidenceById.set(item.id, {
            id: item.id,
            text: item.text,
            sourceId: item.sourceId ?? null,
            topic: claim.topic ?? null,
            sentiment: null,
            evidenceType: null,
            strength: null,
          });
        }
      }
    }

    // Overlay the full rows.
    for (const item of evidence ?? []) {
      evidenceById.set(item.id, {
        id: item.id,
        text: item.text,
        sourceId: item.sourceId ?? null,
        topic: item.topic ?? null,
        sentiment: item.sentiment ?? null,
        evidenceType: item.evidenceType ?? null,
        strength: item.strength ?? null,
      });
    }

    const sourceById = new Map<string, SourceRecord>();
    for (const source of report.sources ?? []) {
      sourceById.set(source.id, reportSourceToRecord(source));
    }
    for (const source of sources ?? []) {
      sourceById.set(source.id, {
        id: source.id,
        url: source.url,
        title: source.title,
        sourceType: source.sourceType,
        channel: source.channel,
        authorityScore: source.authorityScore,
        firstHand: source.firstHand,
        independenceGroupId: source.independenceGroupId,
        status: source.status,
      });
    }

    const claimById = new Map<string, ReportClaim>();
    for (const claim of report.claims ?? []) claimById.set(claim.id, claim);

    return { report, evidenceById, sourceById, claimById, evidenceLoading };
  }, [report, evidence, sources, evidenceLoading]);

  return <ReportDataContext.Provider value={value}>{children}</ReportDataContext.Provider>;
}

function reportSourceToRecord(source: ReportSource): SourceRecord {
  return {
    id: source.id,
    url: source.url,
    title: source.title,
    sourceType: source.sourceType,
    channel: source.channel,
    authorityScore: null,
    firstHand: null,
    independenceGroupId: null,
    status: null,
  };
}
