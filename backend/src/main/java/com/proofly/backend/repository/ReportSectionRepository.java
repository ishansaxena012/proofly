package com.proofly.backend.repository;

import com.proofly.backend.domain.ReportSection;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ReportSectionRepository extends JpaRepository<ReportSection, UUID> {

    List<ReportSection> findByReportIdOrderByOrderIndexAscCreatedAtAsc(UUID reportId);

    void deleteByReportId(UUID reportId);
}
