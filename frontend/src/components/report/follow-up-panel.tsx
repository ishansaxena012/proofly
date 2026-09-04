"use client";

import * as React from "react";
import { Loader2, MessageCircleQuestion } from "lucide-react";

import { ErrorState } from "@/components/common/states";
import { EvidenceCardList } from "@/components/report/evidence-disclosure";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useFollowUp } from "@/lib/queries";

/**
 * Evidence-grounded follow-up (`POST /research/{id}/followup`).
 *
 * The backend restricts the answer to evidence already gathered for this job
 * and returns the evidence ids it cited, which are rendered through the same
 * disclosure UI as the rest of the report — so a follow-up answer is auditable
 * on exactly the same terms as everything above it.
 */
export function FollowUpPanel({ researchJobId }: { researchJobId: string }) {
  const followUp = useFollowUp(researchJobId);
  const [question, setQuestion] = React.useState("");
  const [validationError, setValidationError] = React.useState<string | null>(null);

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setValidationError(null);
    const trimmed = question.trim();
    if (trimmed.length < 5) {
      setValidationError("Ask a full question about this product.");
      return;
    }
    followUp.mutate(trimmed);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageCircleQuestion aria-hidden="true" className="h-4 w-4" />
          Ask a follow-up
        </CardTitle>
        <CardDescription>
          Answered only from the evidence gathered for this job. If the evidence
          doesn&apos;t cover your question, the answer will say so rather than fill the gap.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <form onSubmit={onSubmit} className="space-y-3" noValidate>
          <Label htmlFor="followup-question" className="sr-only">
            Your question
          </Label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              id="followup-question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="How does it hold up for phone calls?"
              disabled={followUp.isPending}
              aria-invalid={validationError ? true : undefined}
              aria-describedby={validationError ? "followup-error" : undefined}
              className="sm:flex-1"
            />
            <Button type="submit" disabled={followUp.isPending}>
              {followUp.isPending ? (
                <>
                  <Loader2 aria-hidden="true" className="animate-spin" />
                  Checking the evidence…
                </>
              ) : (
                "Ask"
              )}
            </Button>
          </div>
          {validationError ? (
            <p id="followup-error" role="alert" className="text-sm text-destructive">
              {validationError}
            </p>
          ) : null}
        </form>

        {followUp.isError ? (
          <ErrorState
            context="answer"
            error={followUp.error}
            onRetry={() => followUp.reset()}
          />
        ) : null}

        {followUp.isSuccess ? (
          <div className="space-y-4 rounded-md border border-border bg-muted/40 p-4">
            <p className="prose-readable">{followUp.data.answer}</p>
            <div>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                Cited evidence
              </h3>
              <EvidenceCardList evidenceIds={followUp.data.citedEvidenceIds ?? []} />
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
