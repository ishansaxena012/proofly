package com.proofly.backend.config;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * All Proofly-specific configuration in one place — every safety/cost limit and every
 * cross-service coordinate is an environment-bound property, never a magic number.
 */
@Validated
@ConfigurationProperties(prefix = "proofly")
public record ProoflyProperties(Ai ai, Research research, Security security) {

    /** Coordinates for the Python AI service (backend → ai-service). */
    public record Ai(
            @NotBlank String baseUrl,
            Duration connectTimeout,
            Duration readTimeout,
            Duration followupTimeout,
            @Min(1) int maxDispatchAttempts,
            Duration dispatchRetryBackoff) {
    }

    /** Job queue / dispatcher / SSE tuning. */
    public record Research(
            @Min(1) int maxConcurrentJobs,
            boolean demoMode,
            @NotBlank String queueKey,
            @NotBlank String eventChannelPrefix,
            Duration sseTimeout,
            Duration sseHeartbeatInterval,
            Duration maxDuration) {

        /** Redis pub/sub channel carrying live events for one job. */
        public String eventChannel(Object jobId) {
            return eventChannelPrefix + jobId;
        }
    }

    /** Service-to-service and end-user authentication settings. */
    public record Security(
            @NotBlank String internalApiKey,
            String jwtIssuerUri,
            String jwtAudience,
            String devUserEmailDomain) {

        /**
         * Dev auth ({@code Authorization: Bearer dev-{userId}}) is only ever active when no
         * JWT issuer is configured. Configuring {@code JWT_ISSUER_URI} disables it outright.
         */
        public boolean devAuthEnabled() {
            return jwtIssuerUri == null || jwtIssuerUri.isBlank();
        }
    }
}
