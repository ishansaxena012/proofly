package com.proofly.backend.service;

import com.proofly.backend.config.ProoflyProperties;
import com.proofly.backend.domain.UserAccount;
import com.proofly.backend.repository.UserAccountRepository;
import com.proofly.backend.security.ProoflyPrincipal;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Creates the local {@code users} row for an already-authenticated identity.
 *
 * <p>Identity itself always comes from the validated token; this only mirrors it into the
 * system of record so research jobs have an owner to reference.
 */
@Service
public class UserProvisioningService {

    private static final Logger log = LoggerFactory.getLogger(UserProvisioningService.class);

    private final UserAccountRepository users;
    private final String devEmailDomain;

    public UserProvisioningService(UserAccountRepository users, ProoflyProperties properties) {
        this.users = users;
        String domain = properties.security().devUserEmailDomain();
        this.devEmailDomain = (domain == null || domain.isBlank()) ? "dev.proofly.local" : domain;
    }

    @Transactional
    public UserAccount ensureUser(ProoflyPrincipal principal) {
        Optional<UserAccount> existing = users.findById(principal.userId());
        if (existing.isPresent()) {
            return existing.get();
        }
        String email = resolveEmail(principal);
        UserAccount created = users.save(new UserAccount(principal.userId(), email, null));
        log.info("Provisioned users row {} on first use (devAuth={})", created.getId(), principal.devAuth());
        return created;
    }

    /**
     * Picks an email that satisfies the unique constraint. If the token's email already
     * belongs to a different account we fall back to a synthetic, id-derived address rather
     * than silently handing the caller somebody else's row.
     */
    private String resolveEmail(ProoflyPrincipal principal) {
        String claimed = principal.email();
        if (claimed == null || claimed.isBlank()) {
            return syntheticEmail(principal);
        }
        Optional<UserAccount> byEmail = users.findByEmailIgnoreCase(claimed);
        if (byEmail.isPresent() && !byEmail.get().getId().equals(principal.userId())) {
            log.warn("Email {} is already bound to another account; provisioning {} with a synthetic address",
                    claimed, principal.userId());
            return syntheticEmail(principal);
        }
        return claimed;
    }

    private String syntheticEmail(ProoflyPrincipal principal) {
        return principal.userId() + "@" + devEmailDomain;
    }
}
