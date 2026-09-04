import { cn, formatConfidence } from "@/lib/utils";

export type ConfidenceBand = "insufficient" | "low" | "moderate" | "high";

export function confidenceBand(confidence: number | null | undefined): ConfidenceBand {
  if (confidence === null || confidence === undefined || Number.isNaN(confidence)) {
    return "insufficient";
  }
  if (confidence < 0.4) return "low";
  if (confidence < 0.7) return "moderate";
  return "high";
}

const BAND_LABEL: Record<ConfidenceBand, string> = {
  insufficient: "Insufficient evidence",
  low: "Low confidence",
  moderate: "Moderate confidence",
  high: "High confidence",
};

const BAND_TEXT: Record<ConfidenceBand, string> = {
  insufficient: "text-muted-foreground",
  low: "text-negative",
  moderate: "text-caution",
  high: "text-positive",
};

const BAND_BAR: Record<ConfidenceBand, string> = {
  insufficient: "bg-muted-foreground/40",
  low: "bg-negative",
  moderate: "bg-caution",
  high: "bg-positive",
};

export function confidenceLabel(confidence: number | null | undefined): string {
  return BAND_LABEL[confidenceBand(confidence)];
}

/**
 * Confidence is a property of the *evidence*, not of the model's certainty, so
 * it is always shown with its qualitative band next to the number.
 */
export function ConfidenceMeter({
  confidence,
  label = "Confidence",
  className,
  showBandLabel = true,
}: {
  confidence: number | null | undefined;
  label?: string;
  className?: string;
  showBandLabel?: boolean;
}) {
  const band = confidenceBand(confidence);
  const percent =
    confidence === null || confidence === undefined || Number.isNaN(confidence)
      ? 0
      : Math.max(0, Math.min(100, Math.round(confidence * 100)));

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3 text-xs">
        <span className="font-medium uppercase tracking-[0.12em] text-muted-foreground">
          {label}
        </span>
        <span className={cn("font-mono tabular-nums", BAND_TEXT[band])}>
          {formatConfidence(confidence)}
        </span>
      </div>
      <div
        role="meter"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${formatConfidence(confidence)} — ${BAND_LABEL[band]}`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn("h-full rounded-full transition-[width]", BAND_BAR[band])}
          style={{ width: `${percent}%` }}
        />
      </div>
      {showBandLabel ? (
        <p className={cn("text-xs", BAND_TEXT[band])}>{BAND_LABEL[band]}</p>
      ) : null}
    </div>
  );
}

/** Score arc. Deliberately plain — the number is the point, not the ornament. */
export function ScoreDial({
  score,
  size = 168,
  className,
}: {
  score: number | null | undefined;
  size?: number;
  className?: string;
}) {
  const hasScore =
    score !== null && score !== undefined && !Number.isNaN(score) && score >= 0;
  const value = hasScore ? Math.max(0, Math.min(100, score)) : 0;

  const stroke = 10;
  const radius = (size - stroke) / 2;
  // 240° sweep, opening downward.
  const sweep = 240;
  const circumference = 2 * Math.PI * radius;
  const arcLength = (sweep / 360) * circumference;
  const filled = (value / 100) * arcLength;

  const tone =
    !hasScore
      ? "stroke-muted-foreground/40"
      : value >= 75
        ? "stroke-positive"
        : value >= 55
          ? "stroke-caution"
          : "stroke-negative";

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-hidden="true"
        className="-rotate-[210deg]"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className="stroke-muted"
          strokeDasharray={`${arcLength} ${circumference}`}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className={tone}
          strokeDasharray={`${filled} ${circumference}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="display text-5xl font-semibold tabular-nums leading-none">
          {hasScore ? Math.round(value) : "—"}
        </span>
        <span className="mt-1.5 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          {hasScore ? "of 100" : "no score"}
        </span>
      </div>
    </div>
  );
}
