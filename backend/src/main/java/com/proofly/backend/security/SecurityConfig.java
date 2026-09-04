package com.proofly.backend.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.api.error.ApiErrorResponse;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.config.ProoflyProperties;
import jakarta.servlet.DispatcherType;
import jakarta.servlet.http.HttpServletResponse;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

/**
 * Two independent filter chains:
 *
 * <ul>
 *   <li>{@code /internal/**} — service-to-service, gated purely on {@code X-Internal-Key}.</li>
 *   <li>everything else — end-user auth, either Supabase JWT (when {@code JWT_ISSUER_URI}
 *       is set) or the dev-only bearer scheme.</li>
 * </ul>
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private static final Logger log = LoggerFactory.getLogger(SecurityConfig.class);

    private static final String[] PUBLIC_PATHS = {
            "/actuator/health", "/actuator/health/**", "/actuator/info",
            "/v3/api-docs", "/v3/api-docs/**", "/swagger-ui.html", "/swagger-ui/**"
    };

    private final ProoflyProperties properties;
    private final ObjectMapper objectMapper;
    private final org.springframework.beans.factory.ObjectProvider<
            com.proofly.backend.service.UserProvisioningService> userProvisioning;

    public SecurityConfig(ProoflyProperties properties,
                          ObjectMapper objectMapper,
                          org.springframework.beans.factory.ObjectProvider<
                                  com.proofly.backend.service.UserProvisioningService> userProvisioning) {
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.userProvisioning = userProvisioning;
    }

    @Bean
    @Order(Ordered.HIGHEST_PRECEDENCE)
    public SecurityFilterChain internalApiFilterChain(HttpSecurity http) throws Exception {
        return http
                .securityMatcher("/internal/**")
                .csrf(csrf -> csrf.disable())
                .cors(cors -> cors.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .anonymous(anonymous -> anonymous.disable())
                .addFilterBefore(new InternalApiKeyFilter(properties, objectMapper),
                        UsernamePasswordAuthenticationFilter.class)
                .authorizeHttpRequests(auth -> auth.anyRequest().hasAuthority(InternalApiKeyFilter.ROLE))
                .exceptionHandling(ex -> ex.authenticationEntryPoint(this::writeForbidden)
                        .accessDeniedHandler((req, res, denied) -> writeForbidden(req, res, null)))
                .build();
    }

    @Bean
    @Order(Ordered.HIGHEST_PRECEDENCE + 10)
    public SecurityFilterChain publicApiFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .cors(Customizer.withDefaults())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        // The SSE endpoint returns an SseEmitter, so the request comes back
                        // through the chain on an ASYNC dispatch once the stream ends. That
                        // dispatch carries no SecurityContext; re-authorising it would deny
                        // an already-committed response and truncate the event stream, so
                        // authorisation is decided on the initial REQUEST dispatch only.
                        .dispatcherTypeMatchers(DispatcherType.ASYNC, DispatcherType.ERROR).permitAll()
                        .requestMatchers(PUBLIC_PATHS).permitAll()
                        .requestMatchers(org.springframework.http.HttpMethod.OPTIONS, "/**").permitAll()
                        .anyRequest().authenticated())
                .exceptionHandling(ex -> ex
                        .authenticationEntryPoint(this::writeUnauthorized)
                        .accessDeniedHandler((req, res, denied) ->
                                write(res, ErrorCode.FORBIDDEN, "Access denied")));

        if (properties.security().devAuthEnabled()) {
            log.warn("*** DEV AUTH ENABLED *** JWT_ISSUER_URI is not configured, so the backend accepts "
                    + "unverified 'Authorization: Bearer dev-{userId}' tokens. This is for local/demo use "
                    + "only — set JWT_ISSUER_URI to enable real Supabase JWT validation.");
            http.addFilterBefore(new DevAuthenticationFilter(properties, userProvisioning),
                    UsernamePasswordAuthenticationFilter.class);
        } else {
            log.info("Validating Supabase JWTs issued by {}", properties.security().jwtIssuerUri());
            http.oauth2ResourceServer(oauth2 -> oauth2
                    // EventSource cannot set headers, so the SSE route also reads ?access_token=.
                    .bearerTokenResolver(BearerTokenSupport::resolveToken)
                    .jwt(jwt -> jwt
                            .decoder(jwtDecoder())
                            .jwtAuthenticationConverter(new JwtPrincipalConverter())));
        }
        return http.build();
    }

    /**
     * Lazily-resolving decoder: the JWKS is fetched on first token validation rather than
     * at startup, so the backend still boots when the issuer is briefly unreachable.
     */
    private JwtDecoder jwtDecoder() {
        String issuer = properties.security().jwtIssuerUri();
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withIssuerLocation(issuer).build();
        String audience = properties.security().jwtAudience();
        if (audience != null && !audience.isBlank()) {
            decoder.setJwtValidator(JwtValidators.createDefaultWithValidators(
                    new org.springframework.security.oauth2.core.OAuth2TokenValidator<>() {
                        @Override
                        public org.springframework.security.oauth2.core.OAuth2TokenValidatorResult validate(
                                org.springframework.security.oauth2.jwt.Jwt token) {
                            return token.getAudience() != null && token.getAudience().contains(audience)
                                    ? org.springframework.security.oauth2.core.OAuth2TokenValidatorResult.success()
                                    : org.springframework.security.oauth2.core.OAuth2TokenValidatorResult.failure(
                                    new org.springframework.security.oauth2.core.OAuth2Error(
                                            "invalid_token", "Required audience " + audience + " missing", null));
                        }
                    }));
        } else {
            decoder.setJwtValidator(JwtValidators.createDefaultWithIssuer(issuer));
        }
        return decoder;
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOriginPatterns(List.of("*"));
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("*"));
        config.setExposedHeaders(List.of("Content-Type", "Cache-Control"));
        config.setMaxAge(3600L);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", config);
        return source;
    }

    private void writeUnauthorized(jakarta.servlet.http.HttpServletRequest request,
                                   HttpServletResponse response,
                                   org.springframework.security.core.AuthenticationException ex) {
        write(response, ErrorCode.UNAUTHORIZED, "Authentication required");
    }

    private void writeForbidden(jakarta.servlet.http.HttpServletRequest request,
                                HttpServletResponse response,
                                org.springframework.security.core.AuthenticationException ex) {
        write(response, ErrorCode.FORBIDDEN, "Invalid or missing " + InternalApiKeyFilter.HEADER + " header");
    }

    private void write(HttpServletResponse response, ErrorCode code, String message) {
        try {
            response.setStatus(code.httpStatus().value());
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            objectMapper.writeValue(response.getOutputStream(), ApiErrorResponse.of(code, message));
        } catch (Exception writeFailure) {
            log.error("Failed to write error response", writeFailure);
        }
    }
}
