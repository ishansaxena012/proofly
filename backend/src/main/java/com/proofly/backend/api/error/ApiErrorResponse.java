package com.proofly.backend.api.error;

import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonIgnore;
import java.time.OffsetDateTime;
import java.util.Map;

/**
 * The single error body shape used by every Proofly service:
 * {@code { "errorCode": "...", "message": "...", "timestamp": "..." }}.
 *
 * <p>{@code details} is flattened onto the top level so responses that the contract
 * requires to carry extra fields (e.g. {@code status} on a 409 report request) stay
 * compatible with the base shape.
 */
public record ApiErrorResponse(
        String errorCode,
        String message,
        OffsetDateTime timestamp,
        @JsonIgnore Map<String, Object> details) {

    public ApiErrorResponse {
        details = details == null ? Map.of() : Map.copyOf(details);
    }

    public static ApiErrorResponse of(ErrorCode errorCode, String message) {
        return new ApiErrorResponse(errorCode.name(), message, OffsetDateTime.now(), Map.of());
    }

    public static ApiErrorResponse of(ErrorCode errorCode, String message, Map<String, Object> details) {
        return new ApiErrorResponse(errorCode.name(), message, OffsetDateTime.now(), details);
    }

    @JsonAnyGetter
    public Map<String, Object> additionalFields() {
        return details;
    }
}
