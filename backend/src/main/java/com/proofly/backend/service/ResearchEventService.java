package com.proofly.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.proofly.backend.api.dto.ResearchEventDto;
import com.proofly.backend.domain.ResearchEvent;
import com.proofly.backend.domain.ResearchEventType;
import com.proofly.backend.repository.ResearchEventRepository;
import com.proofly.backend.sse.ResearchEventPublisher;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/**
 * Appends to the {@code research_events} log and fans the entry out to live SSE
 * subscribers.
 *
 * <p>The Redis publish is deferred until after commit, so a subscriber can never be told
 * about state that a reader would not yet be able to see in Postgres.
 */
@Service
public class ResearchEventService {

    private final ResearchEventRepository events;
    private final ResearchEventPublisher publisher;

    public ResearchEventService(ResearchEventRepository events, ResearchEventPublisher publisher) {
        this.events = events;
        this.publisher = publisher;
    }

    @Transactional
    public ResearchEvent record(UUID researchJobId, ResearchEventType eventType, String message, JsonNode payload) {
        ResearchEvent saved = events.save(new ResearchEvent(researchJobId, eventType, message, payload));
        publishAfterCommit(researchJobId, ResearchEventDto.from(saved));
        return saved;
    }

    @Transactional(readOnly = true)
    public List<ResearchEventDto> history(UUID researchJobId) {
        return events.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId).stream()
                .map(ResearchEventDto::from)
                .toList();
    }

    private void publishAfterCommit(UUID researchJobId, ResearchEventDto dto) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    publisher.publish(researchJobId, dto);
                }
            });
        } else {
            publisher.publish(researchJobId, dto);
        }
    }
}
