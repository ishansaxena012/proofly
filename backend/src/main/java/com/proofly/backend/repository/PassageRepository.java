package com.proofly.backend.repository;

import com.proofly.backend.domain.Passage;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PassageRepository extends JpaRepository<Passage, UUID> {

    List<Passage> findByDocumentIdOrderByPositionAsc(UUID documentId);
}
