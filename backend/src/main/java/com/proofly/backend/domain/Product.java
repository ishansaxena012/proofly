package com.proofly.backend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

/** {@code products} — the single product a research job is about. */
@Entity
@Table(name = "products")
public class Product {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "raw_query", nullable = false)
    private String rawQuery;

    @Column(name = "canonical_name")
    private String canonicalName;

    @Column(name = "brand")
    private String brand;

    @Column(name = "category")
    private String category;

    @Column(name = "model")
    private String model;

    @Column(name = "resolution_confidence")
    private BigDecimal resolutionConfidence;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    protected Product() {
    }

    public Product(String rawQuery) {
        this.rawQuery = rawQuery;
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getRawQuery() {
        return rawQuery;
    }

    public void setRawQuery(String rawQuery) {
        this.rawQuery = rawQuery;
    }

    public String getCanonicalName() {
        return canonicalName;
    }

    public void setCanonicalName(String canonicalName) {
        this.canonicalName = canonicalName;
    }

    public String getBrand() {
        return brand;
    }

    public void setBrand(String brand) {
        this.brand = brand;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getModel() {
        return model;
    }

    public void setModel(String model) {
        this.model = model;
    }

    public BigDecimal getResolutionConfidence() {
        return resolutionConfidence;
    }

    public void setResolutionConfidence(BigDecimal resolutionConfidence) {
        this.resolutionConfidence = resolutionConfidence;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
