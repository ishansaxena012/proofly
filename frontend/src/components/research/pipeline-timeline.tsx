"use client";

import { AlertTriangle, Check, Circle, Loader2, MinusCircle } from "lucide-react";

import type { ResolvedStage, StageState } from "@/lib/stages";
import { cn, formatTimestamp } from "@/lib/utils";

const STATE_LABEL: Record<StageState, string> = {
  pending: "Not started",
  running: "In progress",
  done: "Complete",
  degraded: "No results",
  failed: "Failed",
};

function StageMarker({ state }: { state: StageState }) {
  const base =
    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border bg-background";
  switch (state) {
    case "done":
      return (
        <span className={cn(base, "border-positive/40 bg-positive/10 text-positive")}>
          <Check aria-hidden="true" className="h-4 w-4" />
        </span>
      );
    case "running":
      return (
        <span className={cn(base, "border-primary/40 bg-accent text-accent-foreground")}>
          <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
        </span>
      );
    case "degraded":
      return (
        <span className={cn(base, "border-caution/40 bg-caution/10 text-caution")}>
          <MinusCircle aria-hidden="true" className="h-4 w-4" />
        </span>
      );
    case "failed":
      return (
        <span className={cn(base, "border-negative/40 bg-negative/10 text-negative")}>
          <AlertTriangle aria-hidden="true" className="h-4 w-4" />
        </span>
      );
    default:
      return (
        <span className={cn(base, "border-border text-muted-foreground/50")}>
          <Circle aria-hidden="true" className="h-2 w-2 fill-current" />
        </span>
      );
  }
}

/** Renders the flat, primitive parts of an event payload as chips. */
function PayloadChips({ payload }: { payload: Record<string, unknown> | null }) {
  if (!payload) return null;
  const entries = Object.entries(payload).filter(
    ([, value]) =>
      typeof value === "string" || typeof value === "number" || typeof value === "boolean",
  );
  if (entries.length === 0) return null;

  return (
    <ul className="mt-2 flex flex-wrap gap-1.5">
      {entries.slice(0, 8).map(([key, value]) => (
        <li
          key={key}
          className="rounded border border-border bg-muted/60 px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
        >
          <span className="opacity-70">{key}</span>
          <span aria-hidden="true"> = </span>
          <span className="text-foreground">{String(value)}</span>
        </li>
      ))}
    </ul>
  );
}

export function PipelineTimeline({ stages }: { stages: ResolvedStage[] }) {
  return (
    <ol className="relative space-y-0">
      {stages.map((stage, index) => {
        const isLast = index === stages.length - 1;
        return (
          <li key={stage.id} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast ? (
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-[13px] top-8 h-[calc(100%-2rem)] w-px",
                  stage.state === "done" ? "bg-positive/30" : "bg-border",
                )}
              />
            ) : null}

            <StageMarker state={stage.state} />

            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h3
                  className={cn(
                    "text-sm font-semibold",
                    stage.state === "pending" && "text-muted-foreground",
                  )}
                >
                  {stage.title}
                </h3>
                <span
                  className={cn(
                    "text-[11px] uppercase tracking-[0.12em]",
                    stage.state === "done" && "text-positive",
                    stage.state === "running" && "text-accent-foreground",
                    stage.state === "degraded" && "text-caution",
                    stage.state === "failed" && "text-negative",
                    stage.state === "pending" && "text-muted-foreground",
                  )}
                >
                  {STATE_LABEL[stage.state]}
                </span>
                {stage.event?.createdAt ? (
                  <span className="ml-auto font-mono text-[11px] text-muted-foreground">
                    {formatTimestamp(stage.event.createdAt)}
                  </span>
                ) : null}
              </div>

              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {stage.description}
              </p>

              {stage.detail ? (
                <p
                  className={cn(
                    "mt-2 text-sm",
                    stage.state === "failed"
                      ? "text-negative"
                      : stage.state === "degraded"
                        ? "text-caution"
                        : "text-foreground",
                  )}
                >
                  {stage.detail}
                </p>
              ) : null}

              <PayloadChips payload={stage.event?.payload ?? null} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}
