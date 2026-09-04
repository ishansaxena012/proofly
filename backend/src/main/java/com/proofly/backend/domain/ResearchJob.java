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
import org.hibernate.annotations.UpdateTimestamp;

/** {@code research_jobs} — one job per product query, owned by exactly one user. */
@Entity
@Table(name = "research_jobs")
public class ResearchJob {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "product_id")
    private UUID productId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false)
    private ResearchJobStatus status = ResearchJobStatus.CREATED;

    @Column(name = "current_stage")
    private String currentStage;

    @Column(name = "demo_mode", nullable = false)
    private boolean demoMode;

    @Column(name = "error_code")
    private String errorCode;

    @Column(name = "error_message")
    private String errorMessage;

    @Column(name = "source_count", nullable = false)
    private int sourceCount;

    @Column(name = "evidence_count", nullable = false)
    private int evidenceCount;

    @Column(name = "claim_count", nullable = false)
    private int claimCount;

    @Column(name = "verified_claim_count", nullable = false)
    private int verifiedClaimCount;

    @Column(name = "llm_call_count", nullable = false)
    private int llmCallCount;

    @Column(name = "started_at")
    private OffsetDateTime startedAt;

    @Column(name = "completed_at")
    private OffsetDateTime completedAt;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    protected ResearchJob() {
    }

    public ResearchJob(UUID userId, UUID productId, boolean demoMode) {
        this.userId = userId;
        this.productId = productId;
        this.demoMode = demoMode;
        this.status = ResearchJobStatus.CREATED;
        this.currentStage = ResearchJobStatus.CREATED.name();
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public UUID getUserId() {
        return userId;
    }

    public void setUserId(UUID userId) {
        this.userId = userId;
    }

    public UUID getProductId() {
        return productId;
    }

    public void setProductId(UUID productId) {
        this.productId = productId;
    }

    public ResearchJobStatus getStatus() {
        return status;
    }

    public void setStatus(ResearchJobStatus status) {
        this.status = status;
    }

    public String getCurrentStage() {
        return currentStage;
    }

    public void setCurrentStage(String currentStage) {
        this.currentStage = currentStage;
    }

    public boolean isDemoMode() {
        return demoMode;
    }

    public void setDemoMode(boolean demoMode) {
        this.demoMode = demoMode;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public void setErrorCode(String errorCode) {
        this.errorCode = errorCode;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    public int getSourceCount() {
        return sourceCount;
    }

    public void setSourceCount(int sourceCount) {
        this.sourceCount = sourceCount;
    }

    public int getEvidenceCount() {
        return evidenceCount;
    }

    public void setEvidenceCount(int evidenceCount) {
        this.evidenceCount = evidenceCount;
    }

    public int getClaimCount() {
        return claimCount;
    }

    public void setClaimCount(int claimCount) {
        this.claimCount = claimCount;
    }

    public int getVerifiedClaimCount() {
        return verifiedClaimCount;
    }

    public void setVerifiedClaimCount(int verifiedClaimCount) {
        this.verifiedClaimCount = verifiedClaimCount;
    }

    public int getLlmCallCount() {
        return llmCallCount;
    }

    public void setLlmCallCount(int llmCallCount) {
        this.llmCallCount = llmCallCount;
    }

    public OffsetDateTime getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(OffsetDateTime startedAt) {
        this.startedAt = startedAt;
    }

    public OffsetDateTime getCompletedAt() {
        return completedAt;
    }

    public void setCompletedAt(OffsetDateTime completedAt) {
        this.completedAt = completedAt;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    /** Only for constructing in-memory fixtures; Hibernate owns this column on write. */
    public void setCreatedAt(OffsetDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}
