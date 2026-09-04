package com.proofly.backend.repository;

import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ResearchJobRepository extends JpaRepository<ResearchJob, UUID> {

    /**
     * Ownership-scoped lookup. Every public read path goes through this (or an equivalent
     * {@code userId} predicate) so a job belonging to another user is indistinguishable
     * from a job that does not exist.
     */
    Optional<ResearchJob> findByIdAndUserId(UUID id, UUID userId);

    List<ResearchJob> findByUserIdOrderByCreatedAtDesc(UUID userId);

    List<ResearchJob> findByStatusIn(List<ResearchJobStatus> statuses);
}
