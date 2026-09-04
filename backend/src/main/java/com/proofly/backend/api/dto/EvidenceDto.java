package com.proofly.backend.api.dto;

import com.proofly.backend.domain.Evidence;
import com.proofly.backend.domain.EvidenceStrength;
import com.proofly.backend.domain.EvidenceType;
import com.proofly.backend.domain.Sentiment;
import java.util.UUID;

/** {@code GET /api/v1/research/{id}/evidence} element. */
public record EvidenceDto(
        UUID id,
        UUID sourceId,
        String topic,
        Sentiment sentiment,
        EvidenceType evidenceType,
        EvidenceStrength strength,
        String text) {

    public static EvidenceDto from(Evidence evidence) {
        return new EvidenceDto(
                evidence.getId(),
                evidence.getSourceId(),
                evidence.getTopic(),
                evidence.getSentiment(),
                evidence.getEvidenceType(),
                evidence.getStrength(),
                evidence.getText());
    }
}
