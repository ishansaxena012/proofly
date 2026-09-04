package com.proofly.backend.api.error;

import org.springframework.http.HttpStatus;

/**
 * The closed set of error codes shared by all three Proofly services
 * (docs/API.md §Error shape), together with the HTTP status the backend serves for each.
 */
public enum ErrorCode {

    SOURCE_FAILURE(HttpStatus.BAD_GATEWAY),
    AGENT_FAILURE(HttpStatus.BAD_GATEWAY),
    LLM_FAILURE(HttpStatus.BAD_GATEWAY),
    TIMEOUT(HttpStatus.GATEWAY_TIMEOUT),
    RATE_LIMIT(HttpStatus.TOO_MANY_REQUESTS),
    INVALID_PRODUCT(HttpStatus.BAD_REQUEST),
    INSUFFICIENT_DATA(HttpStatus.CONFLICT),
    NOT_FOUND(HttpStatus.NOT_FOUND),
    VALIDATION_ERROR(HttpStatus.BAD_REQUEST),
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED),
    FORBIDDEN(HttpStatus.FORBIDDEN);

    private final HttpStatus httpStatus;

    ErrorCode(HttpStatus httpStatus) {
        this.httpStatus = httpStatus;
    }

    public HttpStatus httpStatus() {
        return httpStatus;
    }
}
