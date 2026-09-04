package com.proofly.backend.api.internal.dto;

import com.proofly.backend.domain.EvidenceStrength;
import com.proofly.backend.domain.EvidenceType;
import com.proofly.backend.domain.Sentiment;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import java.util.UUID;

/**
 * {@code POST /internal/v1/research/{id}/evidence} — bulk insert.
 *
 * <p>Each item must name its source, either by {@code sourceId} or by {@code sourceUrl}
 * (resolved within the job). Evidence with no resolvable source is rejected rather than
 * stored, because unattributable evidence would break citation traceability.
 */
public record EvidenceBulkRequest(
        @NotEmpty(message = "evidence must not be empty") @Valid List<Item> evidence) {

    public record Item(
            UUID id,
            UUID sourceId,
            String sourceUrl,
            UUID passageId,
            @NotBlank(message = "topic is required") String topic,
            Sentiment sentiment,
            @NotNull(message = "evidenceType is required") EvidenceType evidenceType,
            EvidenceStrength strength,
            @NotBlank(message = "text is required") String text) {
    }
}
