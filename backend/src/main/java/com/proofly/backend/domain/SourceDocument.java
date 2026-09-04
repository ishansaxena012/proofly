package com.proofly.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

/**
 * {@code documents} — the extracted raw text of a fetched source.
 *
 * <p>Named {@code SourceDocument} rather than {@code Document} to avoid colliding with
 * {@code org.w3c.dom.Document} in imports; the table name is still {@code documents}.
 */
@Entity
@Table(name = "documents")
public class SourceDocument {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "source_id", nullable = false)
    private UUID sourceId;

    @Column(name = "raw_text")
    private String rawText;

    @Column(name = "content_hash")
    private String contentHash;

    @Column(name = "token_count")
    private Integer tokenCount;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    protected SourceDocument() {
    }

    public SourceDocument(UUID sourceId, String rawText, String contentHash, Integer tokenCount) {
        this.sourceId = sourceId;
        this.rawText = rawText;
        this.contentHash = contentHash;
        this.tokenCount = tokenCount;
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public UUID getSourceId() {
        return sourceId;
    }

    public void setSourceId(UUID sourceId) {
        this.sourceId = sourceId;
    }

    public String getRawText() {
        return rawText;
    }

    public void setRawText(String rawText) {
        this.rawText = rawText;
    }

    public String getContentHash() {
        return contentHash;
    }

    public void setContentHash(String contentHash) {
        this.contentHash = contentHash;
    }

    public Integer getTokenCount() {
        return tokenCount;
    }

    public void setTokenCount(Integer tokenCount) {
        this.tokenCount = tokenCount;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
