package com.proofly.backend.api.internal.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.proofly.backend.domain.ResearchEventType;
import jakarta.validation.constraints.NotNull;

/** {@code POST /internal/v1/research/{id}/events}. */
public record EventRequest(
        @NotNull(message = "eventType is required") ResearchEventType eventType,
        String message,
        JsonNode payload) {
}
