export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-border py-10">
      <div className="container flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-prose">
          Proofly researches one product at a time and shows its work. Every claim traces
          back to evidence, a passage, and an original source.
        </p>
        <p className="shrink-0 text-xs uppercase tracking-[0.16em]">
          Evidence over opinion
        </p>
      </div>
    </footer>
  );
}
