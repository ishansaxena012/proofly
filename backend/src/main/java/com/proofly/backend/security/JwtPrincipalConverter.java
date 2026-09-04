package com.proofly.backend.security;

import java.util.List;
import java.util.UUID;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.InvalidBearerTokenException;

/**
 * Turns a validated Supabase JWT into a {@link ProoflyPrincipal}. Supabase puts the user
 * id in {@code sub} and the address in {@code email}; both are taken from the signed token
 * only, never from the request.
 */
public class JwtPrincipalConverter implements Converter<Jwt, AbstractAuthenticationToken> {

    @Override
    public AbstractAuthenticationToken convert(Jwt jwt) {
        String subject = jwt.getSubject();
        if (subject == null || subject.isBlank()) {
            throw new InvalidBearerTokenException("Token has no subject claim");
        }
        UUID userId;
        try {
            userId = UUID.fromString(subject);
        } catch (IllegalArgumentException ex) {
            // Non-UUID subjects (custom IdPs) are mapped deterministically so the same
            // subject always resolves to the same users.id.
            userId = UUID.nameUUIDFromBytes(subject.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        String email = jwt.getClaimAsString("email");
        ProoflyPrincipal principal = new ProoflyPrincipal(userId, email, false);
        return new UsernamePasswordAuthenticationToken(
                principal, jwt, List.of(new SimpleGrantedAuthority("ROLE_USER")));
    }
}
