"use client";

import * as React from "react";
import { RefreshCw, TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    // Surfaced in the browser console so the failure is never silent.
    console.error("Unhandled Proofly UI error:", error);
  }, [error]);

  return (
    <div className="container max-w-2xl py-24">
      <Alert variant="destructive">
        <TriangleAlert aria-hidden="true" />
        <AlertTitle>Something broke while rendering this page</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{error.message || "An unexpected client-side error occurred."}</p>
          {error.digest ? (
            <p className="font-mono text-xs opacity-80">Digest: {error.digest}</p>
          ) : null}
          <Button variant="outline" size="sm" onClick={reset}>
            <RefreshCw aria-hidden="true" />
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    </div>
  );
}
