package com.proofly.backend.repository;

import com.proofly.backend.domain.ResearchSource;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ResearchSourceRepository extends JpaRepository<ResearchSource, UUID> {

    List<ResearchSource> findByResearchJobIdOrderByCreatedAtAscIdAsc(UUID researchJobId);

    Optional<ResearchSource> findByResearchJobIdAndUrl(UUID researchJobId, String url);

    long countByResearchJobId(UUID researchJobId);
}
