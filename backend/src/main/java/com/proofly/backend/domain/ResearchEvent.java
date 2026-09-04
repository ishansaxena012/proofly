package com.proofly.backend.domain;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * {@code research_events} — append-only progress log. Every status transition and every
 * internal-API callback appends one row; rows are replayed to late SSE subscribers.
 */
@Entity
@Table(name = "research_events")
public class ResearchEvent {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "research_job_id", nullable = false)
    private UUID researchJobId;

    @Enumerated(EnumType.STRING)
    @Column(name = "event_type", nullable = false)
    private ResearchEventType eventType;

    @Column(name = "message")
    private String message;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "payload")
    private JsonNode payload;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt = OffsetDateTime.now();

    protected ResearchEvent() {
    }

    public ResearchEvent(UUID researchJobId, ResearchEventType eventType, String message, JsonNode payload) {
        this.researchJobId = researchJobId;
        this.eventType = eventType;
        this.message = message;
        this.payload = payload;
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public UUID getResearchJobId() {
        return researchJobId;
    }

    public void setResearchJobId(UUID researchJobId) {
        this.researchJobId = researchJobId;
    }

    public ResearchEventType getEventType() {
        return eventType;
    }

    public void setEventType(ResearchEventType eventType) {
        this.eventType = eventType;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public JsonNode getPayload() {
        return payload;
    }

    public void setPayload(JsonNode payload) {
        this.payload = payload;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
