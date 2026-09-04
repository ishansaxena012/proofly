package com.proofly.backend.repository;

import com.proofly.backend.domain.ResearchEvent;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ResearchEventRepository extends JpaRepository<ResearchEvent, UUID> {

    /** Replay order for late SSE subscribers: chronological, id-tiebroken for stability. */
    List<ResearchEvent> findByResearchJobIdOrderByCreatedAtAscIdAsc(UUID researchJobId);
}
