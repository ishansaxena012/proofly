"use client";

import * as React from "react";
import { ChevronDown, Radio, RadioTower, WifiOff } from "lucide-react";

import { EmptyState } from "@/components/common/states";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { EventStreamStatus } from "@/lib/hooks/use-research-events";
import { eventLabel } from "@/lib/stages";
import type { ResearchEvent } from "@/lib/types";
import { cn, formatTimestamp } from "@/lib/utils";

export function EventStreamIndicator({
  status,
  transport,
}: {
  status: EventStreamStatus;
  transport: "eventsource" | "fetch" | null;
}) {
  const live = status === "open";
  const trying = status === "connecting" || status === "reconnecting";

  const Icon = live ? RadioTower : trying ? Radio : WifiOff;
  const label = live
    ? "Live event stream connected"
    : trying
      ? "Connecting to the event stream…"
      : status === "closed"
        ? "Event stream closed"
        : "Event stream unavailable — falling back to polling";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs",
        live ? "text-positive" : trying ? "text-muted-foreground" : "text-caution",
      )}
      title={transport ? `Transport: ${transport}` : undefined}
    >
      <Icon aria-hidden="true" className={cn("h-3.5 w-3.5", trying && "animate-pulse")} />
      <span aria-live="polite">{label}</span>
    </span>
  );
}

/** The unfiltered event log, exactly as the backend reported it. */
export function EventLog({ events }: { events: ResearchEvent[] }) {
  const [open, setOpen] = React.useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-4 rounded-md border border-border bg-card px-4 py-3 text-left text-sm font-medium transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <span>
          Raw event log
          <span className="ml-2 font-mono text-xs text-muted-foreground">
            {events.length}
          </span>
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
        <div className="mt-3">
          {events.length === 0 ? (
            <EmptyState
              title="No events yet"
              description="Stage events appear here the moment the backend emits them."
            />
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border bg-card">
              {events.map((event) => (
                <li key={event.key} className="flex flex-col gap-1 px-4 py-3 text-sm">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                    <span className="font-mono text-xs font-medium text-foreground">
                      {event.eventType}
                    </span>
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {formatTimestamp(event.createdAt)}
                    </span>
                  </div>
                  <p className="text-muted-foreground">
                    {event.message ?? eventLabel(event.eventType)}
                  </p>
                  {event.payload && Object.keys(event.payload).length > 0 ? (
                    <pre className="mt-1 overflow-x-auto rounded bg-muted/70 p-2 font-mono text-[11px] leading-5 text-muted-foreground">
                      {JSON.stringify(event.payload, null, 2)}
                    </pre>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
