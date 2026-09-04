package com.proofly.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.api.internal.dto.ClaimUpsertRequest;
import com.proofly.backend.api.internal.dto.EventRequest;
import com.proofly.backend.api.internal.dto.EvidenceBulkRequest;
import com.proofly.backend.api.internal.dto.IngestAck;
import com.proofly.backend.api.internal.dto.ProductUpdateRequest;
import com.proofly.backend.api.internal.dto.ReportUpsertRequest;
import com.proofly.backend.api.internal.dto.SourceUpsertRequest;
import com.proofly.backend.api.internal.dto.StatusUpdateRequest;
import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimEvidence;
import com.proofly.backend.domain.ClaimStatus;
import com.proofly.backend.domain.Evidence;
import com.proofly.backend.domain.Product;
import com.proofly.backend.domain.Report;
import com.proofly.backend.domain.ReportSection;
import com.proofly.backend.domain.ResearchEventType;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.domain.ResearchSource;
import com.proofly.backend.domain.SourceStatus;
import com.proofly.backend.repository.ClaimEvidenceRepository;
import com.proofly.backend.repository.ClaimRepository;
import com.proofly.backend.repository.EvidenceRepository;
import com.proofly.backend.repository.ProductRepository;
import com.proofly.backend.repository.ReportRepository;
import com.proofly.backend.repository.ReportSectionRepository;
import com.proofly.backend.repository.ResearchJobRepository;
import com.proofly.backend.repository.ResearchSourceRepository;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Persistence for everything the AI service pushes back through the internal API.
 *
 * <p>Every method is idempotent (the AI service retries callbacks), appends a
 * {@code research_events} row and, through {@link ResearchEventService}, publishes to the
 * job's Redis channel so open SSE streams see the change immediately.
 */
@Service
public class ResearchIngestService {

    private static final Logger log = LoggerFactory.getLogger(ResearchIngestService.class);

    /** Claims counted as "verified" when the AI service does not state a count itself. */
    private static final List<ClaimStatus> VERIFIED_STATUSES =
            List.of(ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED);

    private final ResearchJobRepository jobs;
    private final ProductRepository products;
    private final ResearchSourceRepository sources;
    private final EvidenceRepository evidence;
    private final ClaimRepository claims;
    private final ClaimEvidenceRepository claimEvidence;
    private final ReportRepository reports;
    private final ReportSectionRepository reportSections;
    private final ResearchJobService jobService;
    private final ResearchEventService eventService;
    private final ObjectMapper objectMapper;

    public ResearchIngestService(ResearchJobRepository jobs,
                                 ProductRepository products,
                                 ResearchSourceRepository sources,
                                 EvidenceRepository evidence,
                                 ClaimRepository claims,
                                 ClaimEvidenceRepository claimEvidence,
                                 ReportRepository reports,
                                 ReportSectionRepository reportSections,
                                 ResearchJobService jobService,
                                 ResearchEventService eventService,
                                 ObjectMapper objectMapper) {
        this.jobs = jobs;
        this.products = products;
        this.sources = sources;
        this.evidence = evidence;
        this.claims = claims;
        this.claimEvidence = claimEvidence;
        this.reports = reports;
        this.reportSections = reportSections;
        this.jobService = jobService;
        this.eventService = eventService;
        this.objectMapper = objectMapper;
    }

    // ── status ───────────────────────────────────────────────────────────────

    @Transactional
    public IngestAck updateStatus(UUID researchJobId, StatusUpdateRequest request) {
        ResearchJob job = jobService.transition(researchJobId, request.status(), request.currentStage(),
                request.errorCode(), request.errorMessage());
        if (request.llmCallCount() != null && request.llmCallCount() > job.getLlmCallCount()) {
            job.setLlmCallCount(request.llmCallCount());
            jobs.save(job);
        }
        return IngestAck.ok(researchJobId, job.getStatus());
    }

    // ── product ──────────────────────────────────────────────────────────────

    @Transactional
    public IngestAck updateProduct(UUID researchJobId, ProductUpdateRequest request) {
        ResearchJob job = jobService.requireJob(researchJobId);
        if (job.getProductId() == null) {
            throw new ApiException(ErrorCode.INVALID_PRODUCT,
                    "Research job " + researchJobId + " has no product to resolve");
        }
        Product product = products.findById(job.getProductId())
                .orElseThrow(() -> ApiException.notFound("Product " + job.getProductId() + " was not found"));

        if (request.canonicalName() != null) {
            product.setCanonicalName(request.canonicalName());
        }
        if (request.brand() != null) {
            product.setBrand(request.brand());
        }
        if (request.category() != null) {
            product.setCategory(request.category());
        }
        if (request.model() != null) {
            product.setModel(request.model());
        }
        if (request.resolutionConfidence() != null) {
            product.setResolutionConfidence(request.resolutionConfidence());
        }
        products.save(product);

        eventService.record(researchJobId, ResearchEventType.PRODUCT_IDENTIFIED,
                "Identified product: " + (product.getCanonicalName() == null
                        ? product.getRawQuery() : product.getCanonicalName()),
                objectMapper.valueToTree(Map.of(
                        "productId", product.getId().toString(),
                        "canonicalName", nullSafe(product.getCanonicalName()),
                        "brand", nullSafe(product.getBrand()),
                        "category", nullSafe(product.getCategory()),
                        "model", nullSafe(product.getModel()))));

        return new IngestAck(researchJobId, job.getStatus(), 1, List.of(product.getId()));
    }

    // ── events ───────────────────────────────────────────────────────────────

    @Transactional
    public IngestAck recordEvent(UUID researchJobId, EventRequest request) {
        ResearchJob job = jobService.requireJob(researchJobId);
        var saved = eventService.record(researchJobId, request.eventType(), request.message(), request.payload());
        return new IngestAck(researchJobId, job.getStatus(), 1, List.of(saved.getId()));
    }

    // ── sources ──────────────────────────────────────────────────────────────

    @Transactional
    public IngestAck upsertSources(UUID researchJobId, SourceUpsertRequest request) {
        ResearchJob job = jobService.requireJob(researchJobId);
        List<UUID> ids = new ArrayList<>(request.sources().size());

        for (SourceUpsertRequest.Source payload : request.sources()) {
            ResearchSource entity = resolveSource(researchJobId, payload)
                    .orElseGet(() -> {
                        ResearchSource created =
                                new ResearchSource(researchJobId, payload.channel(), payload.url());
                        if (payload.id() != null) {
                            created.setId(payload.id());
                        }
                        return created;
                    });
            entity.setChannel(payload.channel());
            entity.setUrl(payload.url());
            entity.setTitle(payload.title());
            entity.setSourceType(payload.sourceType());
            entity.setAuthorityScore(payload.authorityScore());
            entity.setFirstHand(payload.firstHand());
            entity.setIndependenceGroupId(payload.independenceGroupId());
            entity.setStatus(payload.status() == null ? SourceStatus.FETCHED : payload.status());
            entity.setFailureReason(payload.failureReason());
            entity.setFetchedAt(payload.fetchedAt() != null ? payload.fetchedAt()
                    : (entity.getStatus() == SourceStatus.FETCHED ? OffsetDateTime.now() : entity.getFetchedAt()));
            ids.add(sources.save(entity).getId());
        }

        job.setSourceCount((int) sources.countByResearchJobId(researchJobId));
        jobs.save(job);
        log.debug("Upserted {} sources for job {}", ids.size(), researchJobId);
        return IngestAck.of(researchJobId, job.getStatus(), ids);
    }

    private Optional<ResearchSource> resolveSource(UUID researchJobId, SourceUpsertRequest.Source payload) {
        if (payload.id() != null) {
            Optional<ResearchSource> byId = sources.findById(payload.id())
                    .filter(existing -> existing.getResearchJobId().equals(researchJobId));
            if (byId.isPresent()) {
                return byId;
            }
        }
        return sources.findByResearchJobIdAndUrl(researchJobId, payload.url());
    }

    // ── evidence ─────────────────────────────────────────────────────────────

    @Transactional
    public IngestAck insertEvidence(UUID researchJobId, EvidenceBulkRequest request) {
        ResearchJob job = jobService.requireJob(researchJobId);

        Map<UUID, ResearchSource> byId = new HashMap<>();
        Map<String, ResearchSource> byUrl = new HashMap<>();
        for (ResearchSource source : sources.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId)) {
            byId.put(source.getId(), source);
            byUrl.putIfAbsent(source.getUrl(), source);
        }

        List<UUID> ids = new ArrayList<>(request.evidence().size());
        for (EvidenceBulkRequest.Item item : request.evidence()) {
            ResearchSource source = resolveEvidenceSource(researchJobId, item, byId, byUrl);
            Evidence entity = item.id() == null ? null : evidence.findById(item.id())
                    .filter(existing -> existing.getResearchJobId().equals(researchJobId))
                    .orElse(null);
            if (entity == null) {
                entity = new Evidence(researchJobId, source.getId(), item.topic(), item.evidenceType(), item.text());
                if (item.id() != null) {
                    entity.setId(item.id());
                }
            }
            entity.setSourceId(source.getId());
            entity.setPassageId(item.passageId());
            entity.setTopic(item.topic());
            entity.setSentiment(item.sentiment());
            entity.setEvidenceType(item.evidenceType());
            entity.setStrength(item.strength());
            entity.setText(item.text());
            ids.add(evidence.save(entity).getId());
        }

        job.setEvidenceCount((int) evidence.countByResearchJobId(researchJobId));
        jobs.save(job);
        log.debug("Stored {} evidence rows for job {}", ids.size(), researchJobId);
        return IngestAck.of(researchJobId, job.getStatus(), ids);
    }

    private ResearchSource resolveEvidenceSource(UUID researchJobId,
                                                 EvidenceBulkRequest.Item item,
                                                 Map<UUID, ResearchSource> byId,
                                                 Map<String, ResearchSource> byUrl) {
        if (item.sourceId() != null) {
            ResearchSource source = byId.get(item.sourceId());
            if (source != null) {
                return source;
            }
        }
        if (item.sourceUrl() != null) {
            ResearchSource source = byUrl.get(item.sourceUrl());
            if (source != null) {
                return source;
            }
        }
        throw new ApiException(ErrorCode.VALIDATION_ERROR,
                "Evidence must reference a source belonging to job " + researchJobId
                        + " (sourceId=" + item.sourceId() + ", sourceUrl=" + item.sourceUrl() + ")");
    }

    // ── claims ───────────────────────────────────────────────────────────────

    @Transactional
    public IngestAck upsertClaims(UUID researchJobId, ClaimUpsertRequest request) {
        ResearchJob job = jobService.requireJob(researchJobId);

        Set<UUID> jobEvidenceIds = new HashSet<>();
        for (Evidence row : evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId)) {
            jobEvidenceIds.add(row.getId());
        }

        // Edges arrive either nested inside a claim or in the top-level claimEvidence
        // array; both are merged per claim, and a claim mentioned by either form has its
        // existing edges replaced wholesale.
        Map<UUID, List<ClaimUpsertRequest.EvidenceLink>> edgesByClaim = new LinkedHashMap<>();
        if (request.claimEvidence() != null) {
            for (ClaimUpsertRequest.ClaimEvidenceLink link : request.claimEvidence()) {
                edgesByClaim.computeIfAbsent(link.claimId(), key -> new ArrayList<>())
                        .add(new ClaimUpsertRequest.EvidenceLink(link.evidenceId(), link.relationship()));
            }
        }

        List<UUID> ids = new ArrayList<>(request.claims().size());
        Set<UUID> handledClaims = new HashSet<>();
        for (ClaimUpsertRequest.Claim payload : request.claims()) {
            Claim entity = payload.id() == null ? null : claims.findById(payload.id())
                    .filter(existing -> existing.getResearchJobId().equals(researchJobId))
                    .orElse(null);
            if (entity == null) {
                entity = new Claim(researchJobId, payload.topic(), payload.statement(), payload.status());
                if (payload.id() != null) {
                    entity.setId(payload.id());
                }
            }
            entity.setTopic(payload.topic());
            entity.setStatement(payload.statement());
            entity.setStatus(payload.status());
            entity.setConfidence(payload.confidence());
            Claim saved = claims.save(entity);
            ids.add(saved.getId());

            List<ClaimUpsertRequest.EvidenceLink> edges = new ArrayList<>();
            boolean declared = false;
            if (payload.evidence() != null) {
                edges.addAll(payload.evidence());
                declared = true;
            }
            List<ClaimUpsertRequest.EvidenceLink> topLevel = edgesByClaim.get(saved.getId());
            if (topLevel != null) {
                edges.addAll(topLevel);
                declared = true;
                handledClaims.add(saved.getId());
            }
            if (declared) {
                replaceClaimEvidence(researchJobId, saved.getId(), edges, jobEvidenceIds);
            }
        }

        // A top-level edge must name a claim of this job — silently dropping one would
        // quietly break a claim's traceability.
        for (Map.Entry<UUID, List<ClaimUpsertRequest.EvidenceLink>> entry : edgesByClaim.entrySet()) {
            if (handledClaims.contains(entry.getKey())) {
                continue;
            }
            Claim existing = claims.findById(entry.getKey())
                    .filter(claim -> claim.getResearchJobId().equals(researchJobId))
                    .orElseThrow(() -> new ApiException(ErrorCode.VALIDATION_ERROR,
                            "claimEvidence references claim " + entry.getKey()
                                    + ", which does not belong to job " + researchJobId));
            replaceClaimEvidence(researchJobId, existing.getId(), entry.getValue(), jobEvidenceIds);
        }

        job.setClaimCount((int) claims.countByResearchJobId(researchJobId));
        job.setVerifiedClaimCount((int) claims.countByResearchJobIdAndStatusIn(researchJobId, VERIFIED_STATUSES));
        jobs.save(job);

        eventService.record(researchJobId, ResearchEventType.CLAIMS_GENERATED,
                "Generated " + job.getClaimCount() + " claims",
                objectMapper.valueToTree(Map.of(
                        "claimCount", job.getClaimCount(),
                        "verifiedClaimCount", job.getVerifiedClaimCount())));

        return IngestAck.of(researchJobId, job.getStatus(), ids);
    }

    private void replaceClaimEvidence(UUID researchJobId, UUID claimId,
                                      List<ClaimUpsertRequest.EvidenceLink> links,
                                      Set<UUID> jobEvidenceIds) {
        claimEvidence.deleteByClaimId(claimId);
        // Deduplicate on (evidenceId, relationship) so a retried callback cannot trip the
        // uniqueness constraint on claim_evidence.
        Map<String, ClaimUpsertRequest.EvidenceLink> unique = new LinkedHashMap<>();
        for (ClaimUpsertRequest.EvidenceLink link : links) {
            if (!jobEvidenceIds.contains(link.evidenceId())) {
                throw new ApiException(ErrorCode.VALIDATION_ERROR,
                        "Evidence " + link.evidenceId() + " does not belong to job " + researchJobId);
            }
            unique.putIfAbsent(link.evidenceId() + "|" + link.relationship(), link);
        }
        for (ClaimUpsertRequest.EvidenceLink link : unique.values()) {
            claimEvidence.save(new ClaimEvidence(claimId, link.evidenceId(), link.relationship()));
        }
    }

    // ── report ───────────────────────────────────────────────────────────────

    @Transactional
    public IngestAck saveReport(UUID researchJobId, ReportUpsertRequest request) {
        ResearchJob job = jobService.requireJob(researchJobId);

        Report report = reports.findByResearchJobId(researchJobId).orElseGet(() -> new Report(researchJobId));
        report.setOverallScore(request.overallScore());
        report.setVerdict(request.verdict());
        report.setConfidence(request.confidence());
        report.setExecutiveSummary(request.executiveSummary());
        report.setGeneratedAt(request.generatedAt() == null ? OffsetDateTime.now() : request.generatedAt());
        report.setVersion(request.version() == null ? report.getVersion() : request.version());
        Report savedReport = reports.save(report);

        reportSections.deleteByReportId(savedReport.getId());
        List<ReportUpsertRequest.Section> sections = request.resolveSections();
        int index = 0;
        for (ReportUpsertRequest.Section section : sections) {
            JsonNode content = section.content() == null ? objectMapper.createObjectNode() : section.content();
            Integer orderIndex = section.orderIndex() == null ? index : section.orderIndex();
            reportSections.save(new ReportSection(savedReport.getId(), section.sectionType(),
                    section.title(), content, orderIndex));
            index++;
        }

        if (request.verifiedClaimCount() != null) {
            job.setVerifiedClaimCount(request.verifiedClaimCount());
        }
        if (request.llmCallCount() != null && request.llmCallCount() > job.getLlmCallCount()) {
            job.setLlmCallCount(request.llmCallCount());
        }
        jobs.save(job);

        ResearchJobStatus finalStatus =
                request.finalStatus() == null ? ResearchJobStatus.COMPLETED : request.finalStatus();
        ResearchJob finalised = jobService.transition(researchJobId, finalStatus, finalStatus.name(), null, null);

        log.info("Stored report {} ({} sections) for job {}; job is now {}",
                savedReport.getId(), sections.size(), researchJobId, finalised.getStatus());
        return new IngestAck(researchJobId, finalised.getStatus(), sections.size(), List.of(savedReport.getId()));
    }

    private static String nullSafe(String value) {
        return value == null ? "" : value;
    }
}
