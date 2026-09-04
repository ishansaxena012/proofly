package com.proofly.backend.api.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** {@code POST /api/v1/research/{id}/followup} body. */
public record FollowupRequest(

        @NotBlank(message = "question must not be blank")
        @Size(min = 3, max = 1000, message = "question must be between 3 and 1000 characters")
        @Schema(example = "How is the microphone quality on calls?",
                requiredMode = Schema.RequiredMode.REQUIRED)
        String question) {
}
