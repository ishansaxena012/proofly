"use client";

import { ExternalLink, Globe, MessageSquare, Youtube } from "lucide-react";

import { EmptyState } from "@/components/common/states";
import { Badge } from "@/components/ui/badge";
import type { ResearchSource, SourceChannel } from "@/lib/types";
import { cn, hostnameOf, humanizeEnum } from "@/lib/utils";

const CHANNEL_ICON: Record<SourceChannel, typeof Globe> = {
  WEB: Globe,
  REDDIT: MessageSquare,
  YOUTUBE: Youtube,
};

export const CHANNEL_LABEL: Record<SourceChannel, string> = {
  WEB: "Web",
  REDDIT: "Reddit",
  YOUTUBE: "YouTube",
};

export function ChannelIcon({
  channel,
  className,
}: {
  channel: SourceChannel | null;
  className?: string;
}) {
  const Icon = channel ? CHANNEL_ICON[channel] : Globe;
  return <Icon aria-hidden="true" className={cn("h-4 w-4", className)} />;
}

export function SourceRow({ source }: { source: ResearchSource }) {
  const failed = source.status !== "FETCHED";

  return (
    <li className="flex flex-col gap-2 px-4 py-3.5 sm:flex-row sm:items-start sm:gap-4">
      <span
        className={cn(
          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
          failed ? "bg-muted text-muted-foreground" : "bg-accent text-accent-foreground",
        )}
      >
        <ChannelIcon channel={source.channel} />
      </span>

      <div className="min-w-0 flex-1">
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="group inline-flex items-baseline gap-1.5 rounded-sm text-sm font-medium underline-offset-4 hover:underline"
        >
          <span className="break-words">{source.title || hostnameOf(source.url)}</span>
          <ExternalLink
            aria-hidden="true"
            className="h-3 w-3 shrink-0 translate-y-px text-muted-foreground"
          />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
        <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
          {hostnameOf(source.url)}
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Badge variant="outline">{CHANNEL_LABEL[source.channel] ?? source.channel}</Badge>
          {source.sourceType ? (
            <Badge variant="secondary">{humanizeEnum(source.sourceType)}</Badge>
          ) : null}
          {source.firstHand ? <Badge variant="positive">First-hand</Badge> : null}
          {typeof source.authorityScore === "number" ? (
            <Badge variant="neutral" title="Authority score, 0–1">
              Authority {source.authorityScore.toFixed(2)}
            </Badge>
          ) : null}
          {failed ? (
            <Badge variant="caution">{humanizeEnum(source.status)}</Badge>
          ) : null}
        </div>
      </div>
    </li>
  );
}

/**
 * Sources grouped by channel. Independence groups are surfaced because
 * near-duplicate/syndicated coverage must not read as independent corroboration.
 */
export function SourcesPanel({ sources }: { sources: ResearchSource[] }) {
  if (sources.length === 0) {
    return (
      <EmptyState
        title="No sources recorded"
        description="No source has been fetched for this job yet."
      />
    );
  }

  const channels: SourceChannel[] = ["WEB", "REDDIT", "YOUTUBE"];
  const grouped = channels
    .map((channel) => ({
      channel,
      items: sources.filter((source) => source.channel === channel),
    }))
    .filter((group) => group.items.length > 0);

  const other = sources.filter(
    (source) => !channels.includes(source.channel as SourceChannel),
  );

  const groupCounts = new Map<string, number>();
  for (const source of sources) {
    if (!source.independenceGroupId) continue;
    groupCounts.set(
      source.independenceGroupId,
      (groupCounts.get(source.independenceGroupId) ?? 0) + 1,
    );
  }
  const clustered = [...groupCounts.values()].filter((count) => count > 1);

  return (
    <div className="space-y-6">
      {clustered.length > 0 ? (
        <p className="rounded-md border border-caution/30 bg-caution/5 px-4 py-3 text-sm text-caution">
          {clustered.reduce((sum, count) => sum + count, 0)} of these sources fall into{" "}
          {clustered.length} near-duplicate cluster{clustered.length === 1 ? "" : "s"}
          {" "}(syndicated or derivative coverage). They are counted once, not many times,
          when confidence is calculated.
        </p>
      ) : null}

      {grouped.map((group) => (
        <section key={group.channel}>
          <h3 className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
            <ChannelIcon channel={group.channel} className="h-3.5 w-3.5" />
            {CHANNEL_LABEL[group.channel]}
            <span className="font-mono normal-case tracking-normal">
              ({group.items.length})
            </span>
          </h3>
          <ul className="divide-y divide-border rounded-md border border-border bg-card">
            {group.items.map((source) => (
              <SourceRow key={source.id} source={source} />
            ))}
          </ul>
        </section>
      ))}

      {other.length > 0 ? (
        <section>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
            Other
          </h3>
          <ul className="divide-y divide-border rounded-md border border-border bg-card">
            {other.map((source) => (
              <SourceRow key={source.id} source={source} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
