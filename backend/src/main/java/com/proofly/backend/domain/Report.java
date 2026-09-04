package com.proofly.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

/** {@code reports} — exactly one report per research job. */
@Entity
@Table(name = "reports")
public class Report {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "research_job_id", nullable = false, unique = true)
    private UUID researchJobId;

    @Column(name = "overall_score")
    private BigDecimal overallScore;

    @Column(name = "verdict")
    private String verdict;

    @Column(name = "confidence")
    private BigDecimal confidence;

    @Column(name = "executive_summary")
    private String executiveSummary;

    @Column(name = "generated_at")
    private OffsetDateTime generatedAt;

    @Column(name = "version", nullable = false)
    private int version = 1;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    protected Report() {
    }

    public Report(UUID researchJobId) {
        this.researchJobId = researchJobId;
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

    public BigDecimal getOverallScore() {
        return overallScore;
    }

    public void setOverallScore(BigDecimal overallScore) {
        this.overallScore = overallScore;
    }

    public String getVerdict() {
        return verdict;
    }

    public void setVerdict(String verdict) {
        this.verdict = verdict;
    }

    public BigDecimal getConfidence() {
        return confidence;
    }

    public void setConfidence(BigDecimal confidence) {
        this.confidence = confidence;
    }

    public String getExecutiveSummary() {
        return executiveSummary;
    }

    public void setExecutiveSummary(String executiveSummary) {
        this.executiveSummary = executiveSummary;
    }

    public OffsetDateTime getGeneratedAt() {
        return generatedAt;
    }

    public void setGeneratedAt(OffsetDateTime generatedAt) {
        this.generatedAt = generatedAt;
    }

    public int getVersion() {
        return version;
    }

    public void setVersion(int version) {
        this.version = version;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
