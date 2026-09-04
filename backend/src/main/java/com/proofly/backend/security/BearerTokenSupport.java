package com.proofly.backend.security;

import jakarta.servlet.http.HttpServletRequest;
import java.util.regex.Pattern;

/**
 * Where a bearer credential may be read from.
 *
 * <p>Normally it must arrive in the {@code Authorization} header. The one exception is the
 * SSE stream: a browser's native {@code EventSource} cannot set request headers, so
 * {@code GET /api/v1/research/{id}/events} additionally accepts the standard
 * {@code ?access_token=} query parameter. That exception is deliberately scoped to exactly
 * that one endpoint — tokens in URLs end up in access logs and referrers, so no other route
 * accepts one.
 */
public final class BearerTokenSupport {

    public static final String ACCESS_TOKEN_PARAM = "access_token";
    public static final String BEARER_PREFIX = "Bearer ";

    private static final Pattern EVENT_STREAM_PATH =
            Pattern.compile("^/api/v\\d+/research/[^/]+/events/?$");

    private BearerTokenSupport() {
    }

    /** True only for {@code GET /api/v1/research/{id}/events}. */
    public static boolean allowsQueryParameterToken(HttpServletRequest request) {
        if (!"GET".equalsIgnoreCase(request.getMethod())) {
            return false;
        }
        String path = request.getRequestURI();
        if (path == null) {
            return false;
        }
        String contextPath = request.getContextPath();
        if (contextPath != null && !contextPath.isEmpty() && path.startsWith(contextPath)) {
            path = path.substring(contextPath.length());
        }
        return EVENT_STREAM_PATH.matcher(path).matches();
    }

    /**
     * Reads the raw bearer credential from the {@code Authorization} header, falling back
     * to {@code ?access_token=} on the SSE endpoint.
     */
    public static String resolveToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith(BEARER_PREFIX)) {
            String token = header.substring(BEARER_PREFIX.length()).trim();
            if (!token.isEmpty()) {
                return token;
            }
        }
        if (allowsQueryParameterToken(request)) {
            String token = request.getParameter(ACCESS_TOKEN_PARAM);
            if (token != null && !token.isBlank()) {
                return token.trim();
            }
        }
        return null;
    }
}
