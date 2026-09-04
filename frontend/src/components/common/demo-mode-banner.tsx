import { FlaskConical } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** Compact inline marker — safe to place next to a title. */
export function DemoModeBadge({ className }: { className?: string }) {
  return (
    <Badge variant="caution" className={cn("uppercase tracking-wide", className)}>
      <FlaskConical aria-hidden="true" className="h-3 w-3" />
      Demo mode
    </Badge>
  );
}

/**
 * Full-width disclosure. Shown on every screen that renders demo-mode output so
 * fixture data can never be mistaken for live research.
 */
export function DemoModeBanner({ className }: { className?: string }) {
  return (
    <Alert variant="warning" className={cn("", className)}>
      <FlaskConical aria-hidden="true" />
      <AlertTitle>Demo mode — this is not live research</AlertTitle>
      <AlertDescription>
        This job ran against deterministic fixture data because provider credentials are
        not configured. The pipeline, evidence handling and scoring are identical to a live
        run, but the sources and quotations come from a fixed sample set and should not be
        treated as current information about a real product.
      </AlertDescription>
    </Alert>
  );
}
