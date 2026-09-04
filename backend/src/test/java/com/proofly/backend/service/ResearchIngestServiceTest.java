package com.proofly.backend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.TestFixtures;
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
import com.proofly.backend.domain.EvidenceRelationship;
import com.proofly.backend.domain.EvidenceType;
import com.proofly.backend.domain.Product;
import com.proofly.backend.domain.Report;
import com.proofly.backend.domain.ReportSection;
import com.proofly.backend.domain.ReportSectionType;
import com.proofly.backend.domain.ResearchEvent;
import com.proofly.backend.domain.ResearchEventType;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.domain.ResearchSource;
import com.proofly.backend.domain.SourceChannel;
import com.proofly.backend.domain.SourceStatus;
import com.proofly.backend.domain.SourceType;
import com.proofly.backend.repository.ClaimEvidenceRepository;
import com.proofly.backend.repository.ClaimRepository;
import com.proofly.backend.repository.EvidenceRepository;
import com.proofly.backend.repository.ProductRepository;
import com.proofly.backend.repository.ReportRepository;
import com.proofly.backend.repository.ReportSectionRepository;
import com.proofly.backend.repository.ResearchJobRepository;
import com.proofly.backend.repository.ResearchSourceRepository;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class ResearchIngestServiceTest {

    private static final UUID JOB = UUID.fromString("77777777-7777-7777-7777-777777777777");
    private static final UUID USER = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final UUID PRODUCT = UUID.fromString("88888888-8888-8888-8888-888888888888");

    @Mock private ResearchJobRepository jobs;
    @Mock private ProductRepository products;
    @Mock private ResearchSourceRepository sources;
    @Mock private EvidenceRepository evidence;
    @Mock private ClaimRepository claims;
    @Mock private ClaimEvidenceRepository claimEvidence;
    @Mock private ReportRepository reports;
    @Mock private ReportSectionRepository reportSections;
    @Mock private ResearchJobService jobService;
    @Mock private ResearchEventService eventService;

    private ResearchIngestService service;
    private ResearchJob job;

    @BeforeEach
    void setUp() {
        service = new ResearchIngestService(jobs, products, sources, evidence, claims, claimEvidence,
                reports, reportSections, jobService, eventService, new ObjectMapper());
        job = TestFixtures.job(JOB, USER, PRODUCT, ResearchJobStatus.RESEARCHING);
        when(jobService.requireJob(JOB)).thenReturn(job);
        when(jobs.save(any(ResearchJob.class))).thenAnswer(call -> call.getArgument(0));
        when(sources.save(any(ResearchSource.class))).thenAnswer(call -> call.getArgument(0));
        when(evidence.save(any(Evidence.class))).thenAnswer(call -> call.getArgument(0));
        when(claims.save(any(Claim.class))).thenAnswer(call -> call.getArgument(0));
        when(claimEvidence.save(any(ClaimEvidence.class))).thenAnswer(call -> call.getArgument(0));
        when(reports.save(any(Report.class))).thenAnswer(call -> call.getArgument(0));
        when(reportSections.save(any(ReportSection.class))).thenAnswer(call -> call.getArgument(0));
        when(eventService.record(any(), any(), any(), any())).thenAnswer(call ->
                new ResearchEvent(call.getArgument(0), call.getArgument(1), call.getArgument(2), call.getArgument(3)));
    }

    // ── status ───────────────────────────────────────────────────────────────

    @Test
    void statusUpdatesDelegateToTheStateMachine() {
        when(jobService.transition(JOB, ResearchJobStatus.VERIFYING, "VERIFYING", null, null)).thenReturn(job);

        IngestAck ack = service.updateStatus(JOB,
                new StatusUpdateRequest(ResearchJobStatus.VERIFYING, "VERIFYING", null, null, 12));

        assertThat(ack.researchJobId()).isEqualTo(JOB);
        assertThat(job.getLlmCallCount()).isEqualTo(12);
        verify(jobService).transition(JOB, ResearchJobStatus.VERIFYING, "VERIFYING", null, null);
    }

    @Test
    void llmCallCountOnlyEverIncreases() {
        job.setLlmCallCount(40);
        when(jobService.transition(any(), any(), any(), any(), any())).thenReturn(job);

        service.updateStatus(JOB, new StatusUpdateRequest(ResearchJobStatus.ANALYZING, null, null, null, 5));

        assertThat(job.getLlmCallCount()).isEqualTo(40);
    }

    // ── product ──────────────────────────────────────────────────────────────

    @Test
    void productResolutionUpdatesTheRowAndEmitsAnEvent() {
        Product product = TestFixtures.product(PRODUCT, "sony xm6");
        when(products.findById(PRODUCT)).thenReturn(Optional.of(product));

        service.updateProduct(JOB, new ProductUpdateRequest("Sony WH-1000XM6", "Sony",
                "Headphones", "WH-1000XM6", new BigDecimal("0.95")));

        assertThat(product.getCanonicalName()).isEqualTo("Sony WH-1000XM6");
        assertThat(product.getRawQuery()).isEqualTo("sony xm6");
        verify(eventService).record(eq(JOB), eq(ResearchEventType.PRODUCT_IDENTIFIED), any(), any());
    }

    // ── events ───────────────────────────────────────────────────────────────

    @Test
    void arbitraryProgressEventsAreAppendedToTheLog() {
        service.recordEvent(JOB, new EventRequest(ResearchEventType.WEB_RESEARCH_COMPLETED, "12 pages", null));

        verify(eventService).record(JOB, ResearchEventType.WEB_RESEARCH_COMPLETED, "12 pages", null);
    }

    // ── sources ──────────────────────────────────────────────────────────────

    @Test
    void sourcesAreUpsertedByUrlAndTheCounterIsRefreshed() {
        UUID existingId = UUID.randomUUID();
        ResearchSource existing = TestFixtures.source(existingId, JOB, "https://example.test/a");
        when(sources.findByResearchJobIdAndUrl(JOB, "https://example.test/a")).thenReturn(Optional.of(existing));
        when(sources.findByResearchJobIdAndUrl(JOB, "https://example.test/b")).thenReturn(Optional.empty());
        when(sources.countByResearchJobId(JOB)).thenReturn(2L);

        IngestAck ack = service.upsertSources(JOB, new SourceUpsertRequest(List.of(
                new SourceUpsertRequest.Source(null, SourceChannel.WEB, "https://example.test/a", "Updated",
                        SourceType.PROFESSIONAL_REVIEW, new BigDecimal("0.9"), true, null, SourceStatus.FETCHED,
                        null, null),
                new SourceUpsertRequest.Source(null, SourceChannel.REDDIT, "https://example.test/b", "New",
                        SourceType.FORUM_POST, null, false, null, SourceStatus.FAILED, "429 from Reddit", null))));

        assertThat(ack.processed()).isEqualTo(2);
        assertThat(ack.ids()).startsWith(existingId);
        assertThat(existing.getTitle()).isEqualTo("Updated");
        assertThat(job.getSourceCount()).isEqualTo(2);
    }

    @Test
    void aCallerSuppliedSourceIdIsHonouredSoEvidenceCanReferenceIt() {
        UUID suppliedId = UUID.randomUUID();
        when(sources.findById(suppliedId)).thenReturn(Optional.empty());
        when(sources.findByResearchJobIdAndUrl(JOB, "https://example.test/c")).thenReturn(Optional.empty());
        when(sources.countByResearchJobId(JOB)).thenReturn(1L);

        IngestAck ack = service.upsertSources(JOB, new SourceUpsertRequest(List.of(
                new SourceUpsertRequest.Source(suppliedId, SourceChannel.YOUTUBE, "https://example.test/c",
                        null, null, null, null, null, null, null, null))));

        assertThat(ack.ids()).containsExactly(suppliedId);
    }

    // ── evidence ─────────────────────────────────────────────────────────────

    @Test
    void evidenceResolvesItsSourceByIdOrByUrl() {
        UUID sourceId = UUID.randomUUID();
        ResearchSource source = TestFixtures.source(sourceId, JOB, "https://example.test/a");
        when(sources.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of(source));
        when(evidence.countByResearchJobId(JOB)).thenReturn(2L);

        service.insertEvidence(JOB, new EvidenceBulkRequest(List.of(
                new EvidenceBulkRequest.Item(null, sourceId, null, null, "Battery", null,
                        EvidenceType.MEASUREMENT, null, "38 hours measured"),
                new EvidenceBulkRequest.Item(null, null, "https://example.test/a", null, "Comfort", null,
                        EvidenceType.CUSTOMER_EXPERIENCE, null, "Comfortable for long flights"))));

        ArgumentCaptor<Evidence> saved = ArgumentCaptor.forClass(Evidence.class);
        verify(evidence, org.mockito.Mockito.times(2)).save(saved.capture());
        assertThat(saved.getAllValues()).allSatisfy(row -> assertThat(row.getSourceId()).isEqualTo(sourceId));
        assertThat(job.getEvidenceCount()).isEqualTo(2);
    }

    @Test
    void unattributableEvidenceIsRejectedRatherThanStored() {
        when(sources.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of());

        assertThatThrownBy(() -> service.insertEvidence(JOB, new EvidenceBulkRequest(List.of(
                new EvidenceBulkRequest.Item(null, UUID.randomUUID(), null, null, "Battery", null,
                        EvidenceType.FACT, null, "Unsourced")))))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.VALIDATION_ERROR);
        verify(evidence, never()).save(any());
    }

    // ── claims ───────────────────────────────────────────────────────────────

    @Test
    void claimsAreUpsertedWithTheirEvidenceEdgesAndCountersUpdated() {
        UUID evidenceId = UUID.randomUUID();
        when(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB))
                .thenReturn(List.of(TestFixtures.evidence(evidenceId, JOB, UUID.randomUUID(), "Battery", "38h")));
        when(claims.countByResearchJobId(JOB)).thenReturn(1L);
        when(claims.countByResearchJobIdAndStatusIn(eq(JOB), any())).thenReturn(1L);

        UUID claimId = UUID.randomUUID();
        service.upsertClaims(JOB, new ClaimUpsertRequest(List.of(
                new ClaimUpsertRequest.Claim(claimId, "Battery", "Battery beats spec", ClaimStatus.SUPPORTED,
                        new BigDecimal("0.9"),
                        List.of(new ClaimUpsertRequest.EvidenceLink(evidenceId, EvidenceRelationship.SUPPORTS),
                                new ClaimUpsertRequest.EvidenceLink(evidenceId,
                                        EvidenceRelationship.SUPPORTS)))),
                null));

        verify(claimEvidence).deleteByClaimId(claimId);
        // The duplicate edge is collapsed, so a retried callback cannot break the constraint.
        verify(claimEvidence, org.mockito.Mockito.times(1)).save(any(ClaimEvidence.class));
        assertThat(job.getClaimCount()).isEqualTo(1);
        assertThat(job.getVerifiedClaimCount()).isEqualTo(1);
        verify(eventService).record(eq(JOB), eq(ResearchEventType.CLAIMS_GENERATED), any(), any());
    }

    @Test
    void edgesMayArriveInTheTopLevelClaimEvidenceArray() {
        UUID supporting = UUID.randomUUID();
        UUID contradicting = UUID.randomUUID();
        when(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of(
                TestFixtures.evidence(supporting, JOB, UUID.randomUUID(), "Microphone", "Clear indoors"),
                TestFixtures.evidence(contradicting, JOB, UUID.randomUUID(), "Microphone", "Bad in wind")));

        UUID claimId = UUID.randomUUID();
        service.upsertClaims(JOB, new ClaimUpsertRequest(
                List.of(new ClaimUpsertRequest.Claim(claimId, "Microphone", "It depends",
                        ClaimStatus.CONTESTED, new BigDecimal("0.6"), null)),
                List.of(new ClaimUpsertRequest.ClaimEvidenceLink(claimId, supporting,
                                EvidenceRelationship.SUPPORTS),
                        new ClaimUpsertRequest.ClaimEvidenceLink(claimId, contradicting,
                                EvidenceRelationship.CONTRADICTS))));

        verify(claimEvidence).deleteByClaimId(claimId);
        ArgumentCaptor<ClaimEvidence> edges = ArgumentCaptor.forClass(ClaimEvidence.class);
        verify(claimEvidence, org.mockito.Mockito.times(2)).save(edges.capture());
        assertThat(edges.getAllValues())
                .extracting(ClaimEvidence::getRelationship)
                .containsExactlyInAnyOrder(EvidenceRelationship.SUPPORTS, EvidenceRelationship.CONTRADICTS);
    }

    @Test
    void aTopLevelEdgeMustNameAClaimOfThisJob() {
        UUID evidenceId = UUID.randomUUID();
        when(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB))
                .thenReturn(List.of(TestFixtures.evidence(evidenceId, JOB, UUID.randomUUID(), "Battery", "38h")));
        UUID foreignClaim = UUID.randomUUID();
        when(claims.findById(foreignClaim)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.upsertClaims(JOB, new ClaimUpsertRequest(
                List.of(new ClaimUpsertRequest.Claim(null, "Battery", "Statement",
                        ClaimStatus.SUPPORTED, null, null)),
                List.of(new ClaimUpsertRequest.ClaimEvidenceLink(foreignClaim, evidenceId,
                        EvidenceRelationship.SUPPORTS)))))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.VALIDATION_ERROR);
    }

    @Test
    void aClaimWithNoEdgeInformationKeepsTheEdgesItAlreadyHas() {
        when(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of());

        service.upsertClaims(JOB, new ClaimUpsertRequest(
                List.of(new ClaimUpsertRequest.Claim(UUID.randomUUID(), "Battery", "Statement",
                        ClaimStatus.SUPPORTED, null, null)),
                null));

        verify(claimEvidence, never()).deleteByClaimId(any());
        verify(claimEvidence, never()).save(any());
    }

    @Test
    void aClaimCannotCiteEvidenceFromAnotherJob() {
        when(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of());

        assertThatThrownBy(() -> service.upsertClaims(JOB, new ClaimUpsertRequest(List.of(
                new ClaimUpsertRequest.Claim(null, "Battery", "Statement", ClaimStatus.SUPPORTED, null,
                        List.of(new ClaimUpsertRequest.EvidenceLink(UUID.randomUUID(),
                                EvidenceRelationship.SUPPORTS)))),
                null)))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.VALIDATION_ERROR);
    }

    // ── report ───────────────────────────────────────────────────────────────

    @Test
    void savingTheReportReplacesSectionsAndFinalisesTheJob() {
        when(reports.findByResearchJobId(JOB)).thenReturn(Optional.empty());
        ResearchJob completed = TestFixtures.job(JOB, USER, PRODUCT, ResearchJobStatus.COMPLETED);
        when(jobService.transition(eq(JOB), eq(ResearchJobStatus.COMPLETED), any(), any(), any()))
                .thenReturn(completed);

        IngestAck ack = service.saveReport(JOB, report(null, List.of(
                new ReportUpsertRequest.Section(ReportSectionType.STRENGTHS, "Strengths", null, null))));

        ArgumentCaptor<Report> report = ArgumentCaptor.forClass(Report.class);
        verify(reports).save(report.capture());
        assertThat(report.getValue().getOverallScore()).isEqualByComparingTo("82");
        assertThat(report.getValue().getGeneratedAt()).isNotNull();
        verify(reportSections).deleteByReportId(report.getValue().getId());
        verify(reportSections).save(any(ReportSection.class));
        assertThat(job.getVerifiedClaimCount()).isEqualTo(7);
        assertThat(job.getLlmCallCount()).isEqualTo(55);
        assertThat(ack.status()).isEqualTo(ResearchJobStatus.COMPLETED);
    }

    @Test
    void aPartialRunCanFinaliseAsPartiallyCompleted() {
        when(reports.findByResearchJobId(JOB)).thenReturn(Optional.empty());
        when(jobService.transition(eq(JOB), eq(ResearchJobStatus.PARTIALLY_COMPLETED), any(), any(), any()))
                .thenReturn(TestFixtures.job(JOB, USER, PRODUCT, ResearchJobStatus.PARTIALLY_COMPLETED));

        IngestAck ack = service.saveReport(JOB, report(ResearchJobStatus.PARTIALLY_COMPLETED, List.of()));

        assertThat(ack.status()).isEqualTo(ResearchJobStatus.PARTIALLY_COMPLETED);
    }

    @Test
    void aReportPostedAsTheFlatDtoShapeStillProducesSections() {
        when(reports.findByResearchJobId(JOB)).thenReturn(Optional.empty());
        when(jobService.transition(eq(JOB), eq(ResearchJobStatus.COMPLETED), any(), any(), any()))
                .thenReturn(TestFixtures.job(JOB, USER, PRODUCT, ResearchJobStatus.COMPLETED));

        ObjectMapper mapper = new ObjectMapper();
        ReportUpsertRequest request = new ReportUpsertRequest(
                mapper.valueToTree(UUID.randomUUID().toString()), mapper.valueToTree(true),
                new BigDecimal("82"), "Recommended", new BigDecimal("0.74"), "Summary",
                mapper.valueToTree(List.of(Map.of("category", "Sound", "score", 88))),
                mapper.valueToTree(List.of(Map.of("text", "Great ANC"))),
                null, null, null, null, null, null,
                mapper.valueToTree(List.of("Commuters")),
                null,
                mapper.valueToTree(List.of("YouTube was unavailable")),
                mapper.valueToTree(List.of()), mapper.valueToTree(List.of()),
                null, null, null, null, null,
                null);

        service.saveReport(JOB, request);

        ArgumentCaptor<ReportSection> saved = ArgumentCaptor.forClass(ReportSection.class);
        verify(reportSections, org.mockito.Mockito.times(4)).save(saved.capture());
        assertThat(saved.getAllValues()).extracting(ReportSection::getSectionType)
                .containsExactly(ReportSectionType.CATEGORY_ANALYSIS, ReportSectionType.STRENGTHS,
                        ReportSectionType.WHO_SHOULD_BUY, ReportSectionType.CAVEATS);
    }

    /**
     * The report body is the public report DTO plus {@code sections}; most of its fields
     * are irrelevant to a given assertion, so tests name only what they care about.
     */
    private static ReportUpsertRequest report(ResearchJobStatus finalStatus,
                                              List<ReportUpsertRequest.Section> sections) {
        return new ReportUpsertRequest(
                null, null,
                new BigDecimal("82"), "Recommended with caveats", new BigDecimal("0.74"), "Summary",
                null, null, null, null, null, null, null, null, null, null, null,
                null, null,
                1, null, finalStatus, 7, 55, sections);
    }
}
