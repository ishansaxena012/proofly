package com.proofly.backend.repository;

import com.proofly.backend.domain.Report;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ReportRepository extends JpaRepository<Report, UUID> {

    Optional<Report> findByResearchJobId(UUID researchJobId);
}
