package com.proofly.backend.api.dto;

import com.proofly.backend.domain.Product;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

/** {@code GET /api/v1/research/{id}} body. */
public record ResearchJobDto(
        UUID id,
        ResearchJobStatus status,
        String currentStage,
        boolean demoMode,
        ProductDto product,
        int sourceCount,
        int evidenceCount,
        int claimCount,
        int verifiedClaimCount,
        String errorCode,
        String errorMessage,
        OffsetDateTime createdAt,
        OffsetDateTime startedAt,
        OffsetDateTime completedAt) {

    public static ResearchJobDto from(ResearchJob job, Product product) {
        return new ResearchJobDto(
                job.getId(),
                job.getStatus(),
                job.getCurrentStage(),
                job.isDemoMode(),
                ProductDto.from(product),
                job.getSourceCount(),
                job.getEvidenceCount(),
                job.getClaimCount(),
                job.getVerifiedClaimCount(),
                job.getErrorCode(),
                job.getErrorMessage(),
                job.getCreatedAt(),
                job.getStartedAt(),
                job.getCompletedAt());
    }
}
