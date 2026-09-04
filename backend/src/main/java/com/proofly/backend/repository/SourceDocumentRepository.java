package com.proofly.backend.repository;

import com.proofly.backend.domain.SourceDocument;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SourceDocumentRepository extends JpaRepository<SourceDocument, UUID> {

    List<SourceDocument> findBySourceId(UUID sourceId);

    List<SourceDocument> findByContentHash(String contentHash);
}
