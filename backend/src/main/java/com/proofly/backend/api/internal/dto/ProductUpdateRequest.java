package com.proofly.backend.api.internal.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import java.math.BigDecimal;

/**
 * {@code POST /internal/v1/research/{id}/product} — the resolved product identity.
 *
 * <p>{@code rawQuery} is deliberately absent: it is what the user typed and is never
 * rewritten by the resolver.
 */
public record ProductUpdateRequest(
        String canonicalName,
        String brand,
        String category,
        String model,
        @DecimalMin(value = "0.0", message = "resolutionConfidence must be between 0 and 1")
        @DecimalMax(value = "1.0", message = "resolutionConfidence must be between 0 and 1")
        BigDecimal resolutionConfidence) {
}
