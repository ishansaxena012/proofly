package com.proofly.backend.domain;

/** SSE / research_events event types (docs/API.md §SSE). */
public enum ResearchEventType {
    PRODUCT_IDENTIFIED,
    RESEARCH_STARTED,
    WEB_RESEARCH_COMPLETED,
    REDDIT_RESEARCH_COMPLETED,
    YOUTUBE_RESEARCH_COMPLETED,
    EVIDENCE_EXTRACTION_STARTED,
    EVIDENCE_EXTRACTION_COMPLETED,
    CLAIMS_GENERATED,
    VERIFICATION_STARTED,
    VERIFICATION_COMPLETED,
    REPORT_GENERATION_STARTED,
    REPORT_COMPLETED,
    JOB_FAILED,
    JOB_PARTIALLY_COMPLETED,
    /** Emitted by the backend itself when the job status changes; not part of the §24 list. */
    STATUS_CHANGED
}
