package com.proofly.backend.repository;

import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimStatus;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ClaimRepository extends JpaRepository<Claim, UUID> {

    List<Claim> findByResearchJobIdOrderByCreatedAtAscIdAsc(UUID researchJobId);

    long countByResearchJobId(UUID researchJobId);

    long countByResearchJobIdAndStatusIn(UUID researchJobId, List<ClaimStatus> statuses);
}
