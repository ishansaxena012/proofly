package com.proofly.backend.service;

import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.domain.ResearchJobStatus;
import java.util.List;
import org.springframework.stereotype.Component;

/**
 * Guards the job state machine from docs/ARCHITECTURE.md §3.
 *
 * <p>The pipeline only ever moves forward. A stage may be skipped (the AI service is free
 * to jump straight from {@code RUNNING} to {@code RESEARCHING} when there is nothing to
 * plan), a terminal state may be entered from anywhere, and nothing may leave a terminal
 * state. Re-asserting the current state is allowed so callback retries are idempotent.
 */
@Component
public class ResearchJobStateMachine {

    private static final List<ResearchJobStatus> PIPELINE = List.of(
            ResearchJobStatus.CREATED,
            ResearchJobStatus.QUEUED,
            ResearchJobStatus.RUNNING,
            ResearchJobStatus.IDENTIFYING_PRODUCT,
            ResearchJobStatus.PLANNING_RESEARCH,
            ResearchJobStatus.RESEARCHING,
            ResearchJobStatus.EXTRACTING_EVIDENCE,
            ResearchJobStatus.ANALYZING,
            ResearchJobStatus.VERIFYING,
            ResearchJobStatus.GENERATING_REPORT);

    public boolean canTransition(ResearchJobStatus from, ResearchJobStatus to) {
        if (from == null || to == null) {
            return false;
        }
        if (from == to) {
            return true;
        }
        if (from.isTerminal()) {
            return false;
        }
        if (to.isTerminal()) {
            return true;
        }
        return PIPELINE.indexOf(to) > PIPELINE.indexOf(from);
    }

    public void requireTransition(ResearchJobStatus from, ResearchJobStatus to) {
        if (!canTransition(from, to)) {
            throw new ApiException(ErrorCode.VALIDATION_ERROR,
                    "Illegal research job state transition " + from + " -> " + to);
        }
    }
}
