package com.proofly.backend.client;

import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ErrorCode;

/** Raised when the AI service is unreachable or answers with a non-2xx status. */
public class AiServiceException extends ApiException {

    public AiServiceException(ErrorCode errorCode, String message, Throwable cause) {
        super(errorCode, message);
        if (cause != null) {
            initCause(cause);
        }
    }

    public static AiServiceException unreachable(String operation, Throwable cause) {
        return new AiServiceException(ErrorCode.AGENT_FAILURE,
                "AI service is unreachable while performing " + operation, cause);
    }

    public static AiServiceException badResponse(String operation, int status, Throwable cause) {
        ErrorCode code = status == 429 ? ErrorCode.RATE_LIMIT : ErrorCode.AGENT_FAILURE;
        return new AiServiceException(code,
                "AI service returned HTTP " + status + " while performing " + operation, cause);
    }
}
