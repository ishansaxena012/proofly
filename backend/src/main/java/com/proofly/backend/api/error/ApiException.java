package com.proofly.backend.api.error;

import java.util.Map;

/**
 * Base type for every error the API deliberately surfaces. Carrying the {@link ErrorCode}
 * means the HTTP status and the wire body are derived in exactly one place
 * ({@link GlobalExceptionHandler}) rather than at each throw site.
 */
public class ApiException extends RuntimeException {

    private final ErrorCode errorCode;
    private final transient Map<String, Object> details;

    public ApiException(ErrorCode errorCode, String message) {
        this(errorCode, message, Map.of());
    }

    public ApiException(ErrorCode errorCode, String message, Map<String, Object> details) {
        super(message);
        this.errorCode = errorCode;
        this.details = details == null ? Map.of() : Map.copyOf(details);
    }

    public ErrorCode getErrorCode() {
        return errorCode;
    }

    /** Extra top-level fields merged into the error body (e.g. {@code status} on a 409). */
    public Map<String, Object> getDetails() {
        return details;
    }

    /** 404 for anything the caller may not see — including jobs owned by somebody else. */
    public static ApiException notFound(String message) {
        return new ApiException(ErrorCode.NOT_FOUND, message);
    }

    public static ApiException validation(String message) {
        return new ApiException(ErrorCode.VALIDATION_ERROR, message);
    }

    public static ApiException unauthorized(String message) {
        return new ApiException(ErrorCode.UNAUTHORIZED, message);
    }
}
