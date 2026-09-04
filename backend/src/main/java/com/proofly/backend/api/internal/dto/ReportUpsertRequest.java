package com.proofly.backend.api.internal.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.proofly.backend.domain.ReportSectionType;
import com.proofly.backend.domain.ResearchJobStatus;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * {@code POST /internal/v1/research/{id}/report} — the full report DTO from docs/API.md
 * plus a {@code sections} array that maps one-to-one onto {@code report_sections}.
 * Persisting this finalises the job: the status moves to {@code finalStatus} (default
 * {@code COMPLETED}) and a {@code REPORT_COMPLETED} event is appended.
 *
 * <p>The scalar fields land on {@code reports}; the narrative fields land on
 * {@code report_sections}. When {@code sections} is supplied it is authoritative; when it
 * is absent the equivalent sections are derived from the flat report-DTO fields, so the
 * endpoint works with either shape.
 *
 * <p>{@code researchJobId}, {@code demoMode}, {@code sources} and {@code claims} are
 * accepted for symmetry with the read-side DTO but deliberately ignored: the job id comes
 * from the path, demo mode is a property of the job, and sources and claims are already
 * rows written through their own endpoints. Echoing them back can never overwrite the
 * system of record.
 */
public record ReportUpsertRequest(
        JsonNode researchJobId,
        JsonNode demoMode,

        @DecimalMin(value = "0.0", message = "overallScore must be between 0 and 100")
        @DecimalMax(value = "100.0", message = "overallScore must be between 0 and 100")
        BigDecimal overallScore,
        String verdict,
        @DecimalMin(value = "0.0", message = "confidence must be between 0 and 1")
        @DecimalMax(value = "1.0", message = "confidence must be between 0 and 1")
        BigDecimal confidence,
        String executiveSummary,

        // Narrative blocks, as they appear in the public report DTO.
        JsonNode categoryScores,
        JsonNode keyStrengths,
        JsonNode keyWeaknesses,
        JsonNode keyFindings,
        JsonNode commonPraise,
        JsonNode commonComplaints,
        JsonNode conflicts,
        JsonNode longTermOwnership,
        JsonNode whoShouldBuy,
        JsonNode whoShouldAvoid,
        JsonNode caveats,

        // Ignored: already owned by other endpoints.
        JsonNode sources,
        JsonNode claims,

        Integer version,
        OffsetDateTime generatedAt,
        ResearchJobStatus finalStatus,
        Integer verifiedClaimCount,
        Integer llmCallCount,

        @Valid List<Section> sections) {

    public record Section(
            @NotNull(message = "sectionType is required") ReportSectionType sectionType,
            String title,
            JsonNode content,
            Integer orderIndex) {
    }

    /**
     * The sections to persist: the explicit {@code sections} array when present, otherwise
     * the flat report-DTO fields projected onto their section types. A field that is absent
     * or JSON null produces no section — a missing section is never invented as an empty one.
     */
    public List<Section> resolveSections() {
        if (sections != null && !sections.isEmpty()) {
            return sections;
        }
        Map<ReportSectionType, JsonNode> flat = new java.util.LinkedHashMap<>();
        flat.put(ReportSectionType.CATEGORY_ANALYSIS, categoryScores);
        flat.put(ReportSectionType.STRENGTHS, keyStrengths);
        flat.put(ReportSectionType.WEAKNESSES, keyWeaknesses);
        flat.put(ReportSectionType.KEY_FINDINGS, keyFindings);
        flat.put(ReportSectionType.COMMON_PRAISE, commonPraise);
        flat.put(ReportSectionType.COMMON_COMPLAINTS, commonComplaints);
        flat.put(ReportSectionType.CONFLICTS, conflicts);
        flat.put(ReportSectionType.LONG_TERM_OWNERSHIP, longTermOwnership);
        flat.put(ReportSectionType.WHO_SHOULD_BUY, whoShouldBuy);
        flat.put(ReportSectionType.WHO_SHOULD_AVOID, whoShouldAvoid);
        flat.put(ReportSectionType.CAVEATS, caveats);

        List<Section> derived = new ArrayList<>();
        int orderIndex = 0;
        for (Map.Entry<ReportSectionType, JsonNode> entry : flat.entrySet()) {
            JsonNode content = entry.getValue();
            if (content == null || content.isNull()
                    || (content.isContainerNode() && content.isEmpty())) {
                continue;
            }
            derived.add(new Section(entry.getKey(), null, content, orderIndex++));
        }
        return List.copyOf(derived);
    }
}
