"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, PlugZap, RefreshCw, SearchX, ShieldAlert } from "lucide-react";

import { ApiError } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Neutral placeholder for a list the backend legitimately returned empty. */
export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border px-6 py-12 text-center",
        className,
      )}
    >
      <div className="text-muted-foreground" aria-hidden="true">
        {icon ?? <SearchX className="h-6 w-6" />}
      </div>
      <p className="text-sm font-medium">{title}</p>
      {description ? (
        <p className="max-w-prose text-sm text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

/**
 * Renders an `ApiError` honestly: an unreachable backend, a missing/foreign
 * job, and a domain error each read differently.
 */
export function ErrorState({
  error,
  onRetry,
  context,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  /** e.g. "report" — used in copy: "Could not load the report." */
  context?: string;
  className?: string;
}) {
  const subject = context ?? "data";

  if (error instanceof ApiError && error.isNetworkError) {
    return (
      <Alert variant="destructive" className={className}>
        <PlugZap aria-hidden="true" />
        <AlertTitle>Backend unreachable</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{error.message}</p>
          <p className="text-xs opacity-80">
            Start the API (<code className="font-mono">docker compose up</code>, or{" "}
            <code className="font-mono">cd backend &amp;&amp; ./mvnw spring-boot:run</code>
            ) and check <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code>.
          </p>
          {onRetry ? (
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RefreshCw aria-hidden="true" />
              Try again
            </Button>
          ) : null}
        </AlertDescription>
      </Alert>
    );
  }

  if (error instanceof ApiError && error.isUnauthorized) {
    return (
      <Alert variant="destructive" className={className}>
        <ShieldAlert aria-hidden="true" />
        <AlertTitle>Session expired</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>Your session is no longer valid. Sign in again to continue.</p>
          <Button variant="outline" size="sm" asChild>
            <Link href="/login">Sign in</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (error instanceof ApiError && error.isNotFound) {
    return (
      <Alert variant="destructive" className={className}>
        <SearchX aria-hidden="true" />
        <AlertTitle>Not found</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            This research job does not exist, or it belongs to a different account. Jobs are
            private to the account that started them.
          </p>
          <Button variant="outline" size="sm" asChild>
            <Link href="/research">Start new research</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const message =
    error instanceof Error ? error.message : `Could not load the ${subject}.`;
  const code = error instanceof ApiError ? error.errorCode : null;

  return (
    <Alert variant="destructive" className={className}>
      <AlertTriangle aria-hidden="true" />
      <AlertTitle>Could not load the {subject}</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>{message}</p>
        {code ? (
          <p className="font-mono text-xs opacity-80">Error code: {code}</p>
        ) : null}
        {onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw aria-hidden="true" />
            Try again
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
