package com.proofly.backend.api.internal.dto;

import com.proofly.backend.domain.ClaimStatus;
import com.proofly.backend.domain.EvidenceRelationship;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

/**
 * {@code POST /internal/v1/research/{id}/claims} — bulk upsert of claims and their
 * evidence edges:
 *
 * <pre>{@code {"claims": [...], "claimEvidence": [{claimId, evidenceId, relationship}]}}</pre>
 *
 * <p>Re-posting a claim replaces that claim's edges wholesale, which is what lets the
 * verification pass rewrite a claim's status and support set. Edges may also be nested
 * inside a claim as {@code "evidence": [{evidenceId, relationship}]}; both forms are
 * accepted and merged.
 */
public record ClaimUpsertRequest(
        @NotEmpty(message = "claims must not be empty") @Valid List<Claim> claims,
        @Valid List<ClaimEvidenceLink> claimEvidence) {

    public record Claim(
            UUID id,
            @NotBlank(message = "topic is required") String topic,
            @NotBlank(message = "statement is required") String statement,
            @NotNull(message = "status is required") ClaimStatus status,
            @DecimalMin(value = "0.0", message = "confidence must be between 0 and 1")
            @DecimalMax(value = "1.0", message = "confidence must be between 0 and 1")
            BigDecimal confidence,
            @Valid List<EvidenceLink> evidence) {
    }

    /** An edge in the top-level {@code claimEvidence} array. */
    public record ClaimEvidenceLink(
            @NotNull(message = "claimId is required") UUID claimId,
            @NotNull(message = "evidenceId is required") UUID evidenceId,
            @NotNull(message = "relationship is required") EvidenceRelationship relationship) {
    }

    /** An edge nested inside a claim, where the claim id is implied. */
    public record EvidenceLink(
            @NotNull(message = "evidenceId is required") UUID evidenceId,
            @NotNull(message = "relationship is required") EvidenceRelationship relationship) {
    }
}
