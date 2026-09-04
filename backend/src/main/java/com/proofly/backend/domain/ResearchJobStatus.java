package com.proofly.backend.domain;

import java.util.EnumSet;
import java.util.Set;

/**
 * Research job state machine (docs/ARCHITECTURE.md §3).
 *
 * <p>{@code CREATED → QUEUED → RUNNING → IDENTIFYING_PRODUCT → PLANNING_RESEARCH →
 * RESEARCHING → EXTRACTING_EVIDENCE → ANALYZING → VERIFYING → GENERATING_REPORT →
 * COMPLETED}, with alternate terminal states {@code PARTIALLY_COMPLETED}, {@code FAILED}
 * and {@code CANCELLED}.
 */
public enum ResearchJobStatus {
    CREATED,
    QUEUED,
    RUNNING,
    IDENTIFYING_PRODUCT,
    PLANNING_RESEARCH,
    RESEARCHING,
    EXTRACTING_EVIDENCE,
    ANALYZING,
    VERIFYING,
    GENERATING_REPORT,
    COMPLETED,
    PARTIALLY_COMPLETED,
    FAILED,
    CANCELLED;

    private static final Set<ResearchJobStatus> TERMINAL =
            EnumSet.of(COMPLETED, PARTIALLY_COMPLETED, FAILED, CANCELLED);

    private static final Set<ResearchJobStatus> REPORT_READY =
            EnumSet.of(COMPLETED, PARTIALLY_COMPLETED);

    public boolean isTerminal() {
        return TERMINAL.contains(this);
    }

    /** True for the states in which {@code GET /api/v1/research/{id}/report} may serve a report. */
    public boolean isReportAvailable() {
        return REPORT_READY.contains(this);
    }
}
