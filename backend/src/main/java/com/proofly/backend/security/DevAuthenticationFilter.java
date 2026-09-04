package com.proofly.backend.security;

import com.proofly.backend.config.ProoflyProperties;
import com.proofly.backend.service.UserProvisioningService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * DEV-ONLY authentication scheme, active <em>only</em> when {@code JWT_ISSUER_URI} is not
 * configured. It accepts {@code Authorization: Bearer dev-{userId}} — and, on the SSE
 * endpoint, {@code ?access_token=dev-{userId}} — where {@code userId} is any UUID, and maps
 * it straight onto {@code users.id}.
 *
 * <p>An unknown dev id is never rejected: the {@code users} row is provisioned on first
 * sight (once per id per process), so a client can mint a stable id from, say, a hash of an
 * email address and simply start using it.
 *
 * <p>This performs no cryptographic verification whatsoever: any caller can claim any user
 * id. It exists so the whole system is runnable end-to-end without a real Supabase Auth
 * project. Configuring {@code JWT_ISSUER_URI} replaces it with real JWT validation, and a
 * loud warning is logged at startup while it is active.
 */
public class DevAuthenticationFilter extends OncePerRequestFilter {

    public static final String DEV_TOKEN_PREFIX = "dev-";

    private static final Logger log = LoggerFactory.getLogger(DevAuthenticationFilter.class);

    private final String devEmailDomain;
    private final ObjectProvider<UserProvisioningService> userProvisioning;
    private final Set<UUID> provisioned = ConcurrentHashMap.newKeySet();

    public DevAuthenticationFilter(ProoflyProperties properties) {
        this(properties, null);
    }

    public DevAuthenticationFilter(ProoflyProperties properties,
                                   ObjectProvider<UserProvisioningService> userProvisioning) {
        String domain = properties.security().devUserEmailDomain();
        this.devEmailDomain = (domain == null || domain.isBlank()) ? "dev.proofly.local" : domain;
        this.userProvisioning = userProvisioning;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {

        if (SecurityContextHolder.getContext().getAuthentication() == null) {
            parseDevUserId(BearerTokenSupport.resolveToken(request)).ifPresent(userId -> {
                ProoflyPrincipal principal =
                        new ProoflyPrincipal(userId, userId + "@" + devEmailDomain, true);
                ensureUserRow(principal);
                var authentication = new UsernamePasswordAuthenticationToken(
                        principal, null, List.of(new SimpleGrantedAuthority("ROLE_USER")));
                authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                SecurityContextHolder.getContext().setAuthentication(authentication);
                log.debug("Dev auth accepted for user {}", userId);
            });
        }
        chain.doFilter(request, response);
    }

    /**
     * Creates the {@code users} row for a dev id we have not seen in this process yet. A
     * failure here is logged and swallowed: the write paths provision the row themselves,
     * so a transient database problem must not turn into an authentication failure.
     */
    private void ensureUserRow(ProoflyPrincipal principal) {
        if (userProvisioning == null || provisioned.contains(principal.userId())) {
            return;
        }
        UserProvisioningService service = userProvisioning.getIfAvailable();
        if (service == null) {
            return;
        }
        try {
            service.ensureUser(principal);
            provisioned.add(principal.userId());
        } catch (RuntimeException ex) {
            log.warn("Could not provision dev user {} up front: {}", principal.userId(), ex.getMessage());
        }
    }

    private static Optional<UUID> parseDevUserId(String token) {
        if (token == null || !token.startsWith(DEV_TOKEN_PREFIX)) {
            return Optional.empty();
        }
        String raw = token.substring(DEV_TOKEN_PREFIX.length());
        try {
            return Optional.of(UUID.fromString(raw));
        } catch (IllegalArgumentException ex) {
            log.debug("Rejected dev token with non-UUID user id");
            return Optional.empty();
        }
    }
}
