"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";

import { ErrorState } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useStartResearch } from "@/lib/queries";

/** Examples are illustrative product names, not results or endorsements. */
const EXAMPLES = [
  "Sony WH-1000XM6",
  "Dyson V15 Detect",
  "Kindle Paperwhite (12th gen)",
  "Fujifilm X100VI",
];

/** Query shapes that describe a category rather than one product. */
const CATEGORY_SIGNALS = [
  /\bbest\b/i,
  /\btop\s*\d+\b/i,
  /\bvs\.?\b/i,
  /\bversus\b/i,
  /\bcompare\b/i,
  /\bunder\s*\$?\d+/i,
  /\bcheapest\b/i,
  /\brecommend/i,
];

export function StartResearchForm() {
  const router = useRouter();
  const startResearch = useStartResearch();

  const [productQuery, setProductQuery] = React.useState("");
  const [validationError, setValidationError] = React.useState<string | null>(null);

  const trimmed = productQuery.trim();
  const looksLikeCategory =
    trimmed.length > 0 && CATEGORY_SIGNALS.some((pattern) => pattern.test(trimmed));

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setValidationError(null);

    if (trimmed.length < 3) {
      setValidationError("Enter the name of a specific product (at least 3 characters).");
      return;
    }
    if (trimmed.length > 200) {
      setValidationError("That query is too long — a product name is enough.");
      return;
    }

    startResearch.mutate(trimmed, {
      onSuccess: (data) => router.push(`/research/${data.researchJobId}`),
    });
  };

  const pending = startResearch.isPending || startResearch.isSuccess;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Which product?</CardTitle>
          <CardDescription>
            Be specific — brand and model. Proofly researches one product, so a category
            (&ldquo;best noise-cancelling headphones&rdquo;) can&apos;t be answered honestly.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="productQuery">Product name</Label>
              <div className="flex flex-col gap-3 sm:flex-row">
                <Input
                  id="productQuery"
                  name="productQuery"
                  autoFocus
                  autoComplete="off"
                  value={productQuery}
                  onChange={(e) => setProductQuery(e.target.value)}
                  placeholder="Sony WH-1000XM6"
                  disabled={pending}
                  aria-invalid={validationError ? true : undefined}
                  aria-describedby={
                    [
                      validationError ? "product-query-error" : null,
                      looksLikeCategory ? "product-query-hint" : null,
                    ]
                      .filter(Boolean)
                      .join(" ") || undefined
                  }
                  className="sm:flex-1"
                />
                <Button type="submit" size="lg" disabled={pending} className="sm:w-auto">
                  {pending ? (
                    <>
                      <Loader2 aria-hidden="true" className="animate-spin" />
                      Starting…
                    </>
                  ) : (
                    <>
                      Start research
                      <ArrowRight aria-hidden="true" />
                    </>
                  )}
                </Button>
              </div>

              {validationError ? (
                <p id="product-query-error" role="alert" className="text-sm text-destructive">
                  {validationError}
                </p>
              ) : null}

              {looksLikeCategory && !validationError ? (
                <p id="product-query-hint" className="text-sm text-caution">
                  That reads like a category or comparison. Proofly researches one specific
                  product — try the exact brand and model instead.
                </p>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                Examples
              </span>
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  disabled={pending}
                  onClick={() => {
                    setProductQuery(example);
                    setValidationError(null);
                  }}
                  className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground disabled:opacity-50"
                >
                  {example}
                </button>
              ))}
            </div>
          </form>
        </CardContent>
      </Card>

      {startResearch.isError ? (
        <ErrorState
          context="research job"
          error={startResearch.error}
          onRetry={() => startResearch.reset()}
        />
      ) : null}
    </div>
  );
}
