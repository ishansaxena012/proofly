package com.proofly.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

/** {@code evidence} — an atomic, source-traceable statement extracted from a passage. */
@Entity
@Table(name = "evidence")
public class Evidence {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "research_job_id", nullable = false)
    private UUID researchJobId;

    @Column(name = "source_id", nullable = false)
    private UUID sourceId;

    @Column(name = "passage_id")
    private UUID passageId;

    @Column(name = "topic", nullable = false)
    private String topic;

    @Enumerated(EnumType.STRING)
    @Column(name = "sentiment")
    private Sentiment sentiment;

    @Enumerated(EnumType.STRING)
    @Column(name = "evidence_type", nullable = false)
    private EvidenceType evidenceType;

    @Enumerated(EnumType.STRING)
    @Column(name = "strength")
    private EvidenceStrength strength;

    @Column(name = "text", nullable = false)
    private String text;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    protected Evidence() {
    }

    public Evidence(UUID researchJobId, UUID sourceId, String topic, EvidenceType evidenceType, String text) {
        this.researchJobId = researchJobId;
        this.sourceId = sourceId;
        this.topic = topic;
        this.evidenceType = evidenceType;
        this.text = text;
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

    public UUID getSourceId() {
        return sourceId;
    }

    public void setSourceId(UUID sourceId) {
        this.sourceId = sourceId;
    }

    public UUID getPassageId() {
        return passageId;
    }

    public void setPassageId(UUID passageId) {
        this.passageId = passageId;
    }

    public String getTopic() {
        return topic;
    }

    public void setTopic(String topic) {
        this.topic = topic;
    }

    public Sentiment getSentiment() {
        return sentiment;
    }

    public void setSentiment(Sentiment sentiment) {
        this.sentiment = sentiment;
    }

    public EvidenceType getEvidenceType() {
        return evidenceType;
    }

    public void setEvidenceType(EvidenceType evidenceType) {
        this.evidenceType = evidenceType;
    }

    public EvidenceStrength getStrength() {
        return strength;
    }

    public void setStrength(EvidenceStrength strength) {
        this.strength = strength;
    }

    public String getText() {
        return text;
    }

    public void setText(String text) {
        this.text = text;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
