package com.proofly.backend.repository;

import com.proofly.backend.domain.ClaimEvidence;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ClaimEvidenceRepository extends JpaRepository<ClaimEvidence, UUID> {

    List<ClaimEvidence> findByClaimId(UUID claimId);

    List<ClaimEvidence> findByClaimIdIn(List<UUID> claimIds);

    void deleteByClaimId(UUID claimId);
}
