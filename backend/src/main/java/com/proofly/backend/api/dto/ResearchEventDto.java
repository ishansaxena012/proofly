package com.proofly.backend.api.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.proofly.backend.domain.ResearchEvent;
import com.proofly.backend.domain.ResearchEventType;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * One entry of the research progress log.
 *
 * <p>On the SSE stream the {@code event:} name is {@link #eventType()} and the {@code data:}
 * payload is this record serialised — {@code {message, payload, createdAt}} per docs/API.md
 * (plus {@code id}/{@code eventType}, which are redundant with the SSE frame but make the
 * same JSON usable outside an event stream).
 */
public record ResearchEventDto(
        UUID id,
        ResearchEventType eventType,
        String message,
        JsonNode payload,
        OffsetDateTime createdAt) {

    public static ResearchEventDto from(ResearchEvent event) {
        return new ResearchEventDto(
                event.getId(),
                event.getEventType(),
                event.getMessage(),
                event.getPayload(),
                event.getCreatedAt());
    }
}
