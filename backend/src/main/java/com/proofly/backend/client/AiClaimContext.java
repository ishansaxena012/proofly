package com.proofly.backend.client;

import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimStatus;
import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

/** A verified claim plus its evidence edges, as sent to the AI service for follow-up Q&amp;A. */
public record AiClaimContext(
        UUID id,
        String topic,
        String statement,
        ClaimStatus status,
        BigDecimal confidence,
        List<UUID> supportingEvidenceIds,
        List<UUID> contradictingEvidenceIds) {

    public static AiClaimContext of(Claim claim, List<UUID> supporting, List<UUID> contradicting) {
        return new AiClaimContext(claim.getId(), claim.getTopic(), claim.getStatement(),
                claim.getStatus(), claim.getConfidence(), supporting, contradicting);
    }
}
