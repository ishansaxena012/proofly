package com.proofly.backend.api.error;

import com.proofly.backend.domain.ResearchJobStatus;
import java.util.Map;

/**
 * Thrown when a report is requested for a job that has not reached
 * {@code COMPLETED}/{@code PARTIALLY_COMPLETED}. Serves {@code 409} and, per docs/API.md,
 * includes the job's current {@code status} in the body.
 */
public class ReportNotReadyException extends ApiException {

    private final ResearchJobStatus status;

    public ReportNotReadyException(ResearchJobStatus status) {
        super(ErrorCode.INSUFFICIENT_DATA,
                "Report is not available while the research job is in status " + status,
                Map.of("status", status.name()));
        this.status = status;
    }

    public ResearchJobStatus getStatus() {
        return status;
    }
}
