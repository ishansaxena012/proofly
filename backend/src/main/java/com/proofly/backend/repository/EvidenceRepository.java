package com.proofly.backend.repository;

import com.proofly.backend.domain.Evidence;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface EvidenceRepository extends JpaRepository<Evidence, UUID> {

    List<Evidence> findByResearchJobIdOrderByCreatedAtAscIdAsc(UUID researchJobId);

    List<Evidence> findByResearchJobIdAndTopicIgnoreCaseOrderByCreatedAtAscIdAsc(UUID researchJobId, String topic);

    long countByResearchJobId(UUID researchJobId);
}
