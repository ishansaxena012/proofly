package com.proofly.backend.api.internal.dto;

import com.proofly.backend.domain.ResearchJobStatus;
import jakarta.validation.constraints.NotNull;

/** {@code POST /internal/v1/research/{id}/status}. */
public record StatusUpdateRequest(
        @NotNull(message = "status is required") ResearchJobStatus status,
        String currentStage,
        String errorCode,
        String errorMessage,
        Integer llmCallCount) {
}
