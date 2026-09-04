package com.proofly.backend.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * {@code POST /api/v1/research} body.
 *
 * @param productQuery the one product to research, as typed by the user
 * @param demoMode     optional override of the server's {@code DEMO_MODE} default; when
 *                     omitted the server default applies
 */
public record CreateResearchRequest(

        @NotBlank(message = "productQuery must not be blank")
        @Size(min = 2, max = 500, message = "productQuery must be between 2 and 500 characters")
        @Schema(example = "Sony WH-1000XM6", requiredMode = Schema.RequiredMode.REQUIRED)
        String productQuery,

        @Schema(description = "Optional override of the server DEMO_MODE default", nullable = true)
        Boolean demoMode) {
}
