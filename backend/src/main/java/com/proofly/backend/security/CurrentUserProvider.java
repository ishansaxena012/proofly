package com.proofly.backend.security;

import com.proofly.backend.api.error.ApiException;
import java.util.Optional;
import java.util.UUID;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

/**
 * Reads the authenticated identity out of the security context. Services depend on this
 * rather than on {@code SecurityContextHolder} directly so they stay unit-testable.
 */
@Component
public class CurrentUserProvider {

    public Optional<ProoflyPrincipal> currentPrincipal() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()) {
            return Optional.empty();
        }
        if (authentication.getPrincipal() instanceof ProoflyPrincipal principal) {
            return Optional.of(principal);
        }
        return Optional.empty();
    }

    public ProoflyPrincipal requirePrincipal() {
        return currentPrincipal()
                .orElseThrow(() -> ApiException.unauthorized("No authenticated user on this request"));
    }

    public UUID requireUserId() {
        return requirePrincipal().userId();
    }
}
