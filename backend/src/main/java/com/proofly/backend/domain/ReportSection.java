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

/** {@code report_sections} — one typed, JSON-bodied block of a report. */
@Entity
@Table(name = "report_sections")
public class ReportSection {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id = UUID.randomUUID();

    @Column(name = "report_id", nullable = false)
    private UUID reportId;

    @Enumerated(EnumType.STRING)
    @Column(name = "section_type", nullable = false)
    private ReportSectionType sectionType;

    @Column(name = "title")
    private String title;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "content", nullable = false)
    private JsonNode content;

    @Column(name = "order_index")
    private Integer orderIndex;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    protected ReportSection() {
    }

    public ReportSection(UUID reportId, ReportSectionType sectionType, String title, JsonNode content,
                         Integer orderIndex) {
        this.reportId = reportId;
        this.sectionType = sectionType;
        this.title = title;
        this.content = content;
        this.orderIndex = orderIndex;
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public UUID getReportId() {
        return reportId;
    }

    public void setReportId(UUID reportId) {
        this.reportId = reportId;
    }

    public ReportSectionType getSectionType() {
        return sectionType;
    }

    public void setSectionType(ReportSectionType sectionType) {
        this.sectionType = sectionType;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public JsonNode getContent() {
        return content;
    }

    public void setContent(JsonNode content) {
        this.content = content;
    }

    public Integer getOrderIndex() {
        return orderIndex;
    }

    public void setOrderIndex(Integer orderIndex) {
        this.orderIndex = orderIndex;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
