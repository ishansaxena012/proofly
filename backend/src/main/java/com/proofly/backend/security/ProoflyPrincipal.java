package com.proofly.backend.security;

import java.util.UUID;

/**
 * The authenticated caller, already resolved to a {@code users.id}. This is the only
 * source of user identity in the system — a user id supplied in a request body or path is
 * never trusted.
 *
 * @param userId  the {@code users.id} this request acts as
 * @param email   best-known email for the account (used only when provisioning the row)
 * @param devAuth true when the identity came from the dev-only bearer scheme rather than a
 *                validated JWT
 */
public record ProoflyPrincipal(UUID userId, String email, boolean devAuth) {

    public ProoflyPrincipal {
        if (userId == null) {
            throw new IllegalArgumentException("userId is required");
        }
    }

    @Override
    public String toString() {
        return "ProoflyPrincipal[userId=" + userId + ", devAuth=" + devAuth + "]";
    }
}
