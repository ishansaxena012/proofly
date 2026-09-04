import { Suspense } from "react";

import { RequireAuth } from "@/components/auth/require-auth";
import { Skeleton } from "@/components/ui/skeleton";

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="container space-y-4 py-16" aria-busy="true">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-48 w-full" />
        </div>
      }
    >
      <RequireAuth>{children}</RequireAuth>
    </Suspense>
  );
}
