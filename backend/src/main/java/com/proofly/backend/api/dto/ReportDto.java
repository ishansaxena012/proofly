package com.proofly.backend.api.dto;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * The flagship report payload (docs/API.md §Report DTO shape).
 *
 * <p>Every narrative element carries the evidence or claim ids it came from, so the UI can
 * make each statement traceable back to a passage, a source and a URL.
 */
public record ReportDto(
        UUID researchJobId,
        boolean demoMode,
        BigDecimal overallScore,
        String verdict,
        BigDecimal confidence,
        String executiveSummary,
        List<CategoryScoreDto> categoryScores,
        List<EvidenceBackedTextDto> keyStrengths,
        List<EvidenceBackedTextDto> keyWeaknesses,
        List<KeyFindingDto> keyFindings,
        List<EvidenceBackedTextDto> commonPraise,
        List<EvidenceBackedTextDto> commonComplaints,
        List<ConflictDto> conflicts,
        EvidenceBackedTextDto longTermOwnership,
        List<String> whoShouldBuy,
        List<String> whoShouldAvoid,
        List<String> caveats,
        List<ReportSourceDto> sources,
        List<ReportClaimDto> claims,
        OffsetDateTime generatedAt,
        int version) {
}
