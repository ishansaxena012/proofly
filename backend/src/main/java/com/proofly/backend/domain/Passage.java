package com.proofly.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

/**
 * {@code passages} — chunked document text plus its pgvector embedding.
 *
 * <p>Embeddings are produced and written by the Python AI service (it owns the embedding
 * model and writes passages directly). The backend never writes {@code embedding}, so the
 * column is mapped read-only as its Postgres text representation
 * ({@code [0.1,0.2,...]}); this keeps the entity complete without pulling a
 * {@code vector}-aware JDBC type into the backend.
 */
@Entity
@Table(name = "passages")
public class Passage {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "document_id", nullable = false)
    private UUID documentId;

    @Column(name = "text", nullable = false)
    private String text;

    @Column(name = "embedding", insertable = false, updatable = false,
            columnDefinition = "vector(768)")
    private String embedding;

    @Column(name = "`position`")
    private Integer position;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    protected Passage() {
    }

    public Passage(UUID documentId, String text, Integer position) {
        this.documentId = documentId;
        this.text = text;
        this.position = position;
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public UUID getDocumentId() {
        return documentId;
    }

    public void setDocumentId(UUID documentId) {
        this.documentId = documentId;
    }

    public String getText() {
        return text;
    }

    public void setText(String text) {
        this.text = text;
    }

    /** Postgres text form of the {@code vector(768)} column, or {@code null} if not embedded. */
    public String getEmbedding() {
        return embedding;
    }

    public Integer getPosition() {
        return position;
    }

    public void setPosition(Integer position) {
        this.position = position;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
