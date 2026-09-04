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

/**
 * {@code claim_evidence} — the traceability edge between a claim and the evidence that
 * supports, contradicts or contextualises it. Contradicting edges are what let the report
 * preserve conflicts instead of averaging them away.
 */
@Entity
@Table(name = "claim_evidence")
public class ClaimEvidence {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "claim_id", nullable = false)
    private UUID claimId;

    @Column(name = "evidence_id", nullable = false)
    private UUID evidenceId;

    @Enumerated(EnumType.STRING)
    @Column(name = "relationship", nullable = false)
    private EvidenceRelationship relationship;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    protected ClaimEvidence() {
    }

    public ClaimEvidence(UUID claimId, UUID evidenceId, EvidenceRelationship relationship) {
        this.claimId = claimId;
        this.evidenceId = evidenceId;
        this.relationship = relationship;
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public UUID getClaimId() {
        return claimId;
    }

    public void setClaimId(UUID claimId) {
        this.claimId = claimId;
    }

    public UUID getEvidenceId() {
        return evidenceId;
    }

    public void setEvidenceId(UUID evidenceId) {
        this.evidenceId = evidenceId;
    }

    public EvidenceRelationship getRelationship() {
        return relationship;
    }

    public void setRelationship(EvidenceRelationship relationship) {
        this.relationship = relationship;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
