package com.proofly.backend.api.dto;

import com.proofly.backend.domain.ClaimStatus;
import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public record ReportClaimDto(
        UUID id,
        String topic,
        String statement,
        ClaimStatus status,
        BigDecimal confidence,
        List<ClaimEvidenceDto> supportingEvidence,
        List<ClaimEvidenceDto> contradictingEvidence,
        List<ClaimEvidenceDto> contextualisingEvidence) {

    /** The evidence excerpt as it appears under a claim in the report. */
    public record ClaimEvidenceDto(UUID id, String text, UUID sourceId) {
    }
}
