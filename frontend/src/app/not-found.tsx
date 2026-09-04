import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="container flex max-w-xl flex-col items-start py-24">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
        404
      </p>
      <h1 className="display mt-4 text-3xl font-semibold">This page doesn&apos;t exist</h1>
      <p className="prose-readable mt-3">
        The address you followed doesn&apos;t match any page in Proofly. If you were looking
        for a research job, open it from your research history or start a new one.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Button asChild>
          <Link href="/research">Start research</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/">Back to overview</Link>
        </Button>
      </div>
    </div>
  );
}
