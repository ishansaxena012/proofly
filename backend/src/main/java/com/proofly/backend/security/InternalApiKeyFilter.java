package com.proofly.backend.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.api.error.ApiErrorResponse;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.config.ProoflyProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Gate for {@code /internal/**}: the AI service must present
 * {@code X-Internal-Key: {INTERNAL_API_KEY}}. Anything else is rejected with {@code 403}
 * before the request reaches a controller.
 */
public class InternalApiKeyFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-Internal-Key";
    public static final String ROLE = "ROLE_INTERNAL_SERVICE";

    private static final Logger log = LoggerFactory.getLogger(InternalApiKeyFilter.class);

    private final String expectedKey;
    private final ObjectMapper objectMapper;

    public InternalApiKeyFilter(ProoflyProperties properties, ObjectMapper objectMapper) {
        this.expectedKey = properties.security().internalApiKey();
        this.objectMapper = objectMapper;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {

        String presented = request.getHeader(HEADER);
        if (!matches(presented)) {
            log.warn("Rejected internal API call to {} {} — missing or invalid {} header",
                    request.getMethod(), request.getRequestURI(), HEADER);
            writeForbidden(response);
            return;
        }

        var authentication = new UsernamePasswordAuthenticationToken(
                "ai-service", null, List.of(new SimpleGrantedAuthority(ROLE)));
        SecurityContextHolder.getContext().setAuthentication(authentication);
        try {
            chain.doFilter(request, response);
        } finally {
            SecurityContextHolder.clearContext();
        }
    }

    private boolean matches(String presented) {
        if (presented == null || expectedKey == null || expectedKey.isBlank()) {
            return false;
        }
        // Constant-time comparison so the key cannot be recovered by timing the endpoint.
        byte[] a = presented.getBytes(StandardCharsets.UTF_8);
        byte[] b = expectedKey.getBytes(StandardCharsets.UTF_8);
        return java.security.MessageDigest.isEqual(a, b);
    }

    private void writeForbidden(HttpServletResponse response) throws IOException {
        response.setStatus(HttpStatus.FORBIDDEN.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        objectMapper.writeValue(response.getOutputStream(),
                ApiErrorResponse.of(ErrorCode.FORBIDDEN, "Invalid or missing " + HEADER + " header"));
    }
}
