"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/research", label: "New research" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const { session, loading, signOut, mode } = useAuth();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="container flex h-16 items-center justify-between gap-4">
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="flex items-baseline gap-2 rounded-sm"
            aria-label="Proofly home"
          >
            <span className="display text-xl font-semibold tracking-tight">Proofly</span>
            <span className="hidden text-[11px] uppercase tracking-[0.18em] text-muted-foreground sm:inline">
              Product research
            </span>
          </Link>
          <nav aria-label="Primary" className="hidden items-center gap-6 md:flex">
            {NAV.map((item) => {
              const active =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-sm text-sm transition-colors hover:text-foreground",
                    active ? "font-medium text-foreground" : "text-muted-foreground",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          {loading ? (
            <div className="h-9 w-24 animate-pulse rounded-md bg-muted" aria-hidden />
          ) : session ? (
            <>
              <span
                className="hidden max-w-[18ch] truncate text-sm text-muted-foreground sm:inline"
                title={session.email}
              >
                {session.displayName || session.email}
              </span>
              {mode === "dev" ? (
                <span className="hidden rounded-full border border-caution/40 bg-caution/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-caution lg:inline">
                  Dev session
                </span>
              ) : null}
              <Button variant="ghost" size="sm" onClick={() => void signOut()}>
                <LogOut aria-hidden="true" />
                Sign out
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/login">Sign in</Link>
              </Button>
              <Button size="sm" asChild>
                <Link href="/signup">Create account</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
