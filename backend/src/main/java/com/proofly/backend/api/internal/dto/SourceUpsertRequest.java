package com.proofly.backend.api.internal.dto;

import com.proofly.backend.domain.SourceChannel;
import com.proofly.backend.domain.SourceStatus;
import com.proofly.backend.domain.SourceType;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * {@code POST /internal/v1/research/{id}/sources} — bulk upsert.
 *
 * <p>Rows are matched on the caller-supplied {@code id} when present, otherwise on
 * {@code (researchJobId, url)}, so re-posting the same batch is idempotent.
 */
public record SourceUpsertRequest(
        @NotEmpty(message = "sources must not be empty") @Valid List<Source> sources) {

    public record Source(
            UUID id,
            @NotNull(message = "channel is required") SourceChannel channel,
            @NotBlank(message = "url is required") String url,
            String title,
            SourceType sourceType,
            @DecimalMin(value = "0.0", message = "authorityScore must be between 0 and 1")
            @DecimalMax(value = "1.0", message = "authorityScore must be between 0 and 1")
            BigDecimal authorityScore,
            Boolean firstHand,
            UUID independenceGroupId,
            SourceStatus status,
            String failureReason,
            OffsetDateTime fetchedAt) {
    }
}
