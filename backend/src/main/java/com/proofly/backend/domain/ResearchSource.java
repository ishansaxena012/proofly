package com.proofly.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

/** {@code research_sources} — one row per URL the agent attempted to use. */
@Entity
@Table(name = "research_sources")
public class ResearchSource {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "research_job_id", nullable = false)
    private UUID researchJobId;

    @Enumerated(EnumType.STRING)
    @Column(name = "channel", nullable = false)
    private SourceChannel channel;

    @Column(name = "url", nullable = false)
    private String url;

    @Column(name = "title")
    private String title;

    @Enumerated(EnumType.STRING)
    @Column(name = "source_type")
    private SourceType sourceType;

    @Column(name = "authority_score")
    private BigDecimal authorityScore;

    @Column(name = "first_hand")
    private Boolean firstHand;

    @Column(name = "independence_group_id")
    private UUID independenceGroupId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false)
    private SourceStatus status = SourceStatus.FETCHED;

    @Column(name = "failure_reason")
    private String failureReason;

    @Column(name = "fetched_at")
    private OffsetDateTime fetchedAt;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    protected ResearchSource() {
    }

    public ResearchSource(UUID researchJobId, SourceChannel channel, String url) {
        this.researchJobId = researchJobId;
        this.channel = channel;
        this.url = url;
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

    public SourceChannel getChannel() {
        return channel;
    }

    public void setChannel(SourceChannel channel) {
        this.channel = channel;
    }

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public SourceType getSourceType() {
        return sourceType;
    }

    public void setSourceType(SourceType sourceType) {
        this.sourceType = sourceType;
    }

    public BigDecimal getAuthorityScore() {
        return authorityScore;
    }

    public void setAuthorityScore(BigDecimal authorityScore) {
        this.authorityScore = authorityScore;
    }

    public Boolean getFirstHand() {
        return firstHand;
    }

    public void setFirstHand(Boolean firstHand) {
        this.firstHand = firstHand;
    }

    public UUID getIndependenceGroupId() {
        return independenceGroupId;
    }

    public void setIndependenceGroupId(UUID independenceGroupId) {
        this.independenceGroupId = independenceGroupId;
    }

    public SourceStatus getStatus() {
        return status;
    }

    public void setStatus(SourceStatus status) {
        this.status = status;
    }

    public String getFailureReason() {
        return failureReason;
    }

    public void setFailureReason(String failureReason) {
        this.failureReason = failureReason;
    }

    public OffsetDateTime getFetchedAt() {
        return fetchedAt;
    }

    public void setFetchedAt(OffsetDateTime fetchedAt) {
        this.fetchedAt = fetchedAt;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
