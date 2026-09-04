"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Client-side gate for `/research*`.
 *
 * The bearer credential lives in the browser (Supabase session or dev stub), so
 * the gate is necessarily client-side. It is a routing convenience only — the
 * backend is the authority and enforces ownership on every job, report, source
 * and evidence lookup.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  React.useEffect(() => {
    if (loading || session) return;
    const query = searchParams.toString();
    const next = query ? `${pathname}?${query}` : pathname;
    router.replace(`/login?next=${encodeURIComponent(next)}`);
  }, [loading, session, router, pathname, searchParams]);

  if (loading) return <AuthGateSkeleton label="Checking your session…" />;
  if (!session) return <AuthGateSkeleton label="Redirecting to sign in…" />;

  return <>{children}</>;
}

function AuthGateSkeleton({ label }: { label: string }) {
  return (
    <div className="container py-16" aria-busy="true" aria-live="polite">
      <p className="sr-only">{label}</p>
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96 max-w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    </div>
  );
}
