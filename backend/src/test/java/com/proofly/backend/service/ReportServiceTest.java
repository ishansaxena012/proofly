package com.proofly.backend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.TestFixtures;
import com.proofly.backend.api.dto.ReportDto;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.api.error.ReportNotReadyException;
import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimEvidence;
import com.proofly.backend.domain.ClaimStatus;
import com.proofly.backend.domain.EvidenceRelationship;
import com.proofly.backend.domain.Report;
import com.proofly.backend.domain.ReportSection;
import com.proofly.backend.domain.ReportSectionType;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.repository.ClaimEvidenceRepository;
import com.proofly.backend.repository.ClaimRepository;
import com.proofly.backend.repository.EvidenceRepository;
import com.proofly.backend.repository.ReportRepository;
import com.proofly.backend.repository.ReportSectionRepository;
import com.proofly.backend.repository.ResearchSourceRepository;
import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class ReportServiceTest {

    private static final UUID JOB = UUID.fromString("44444444-4444-4444-4444-444444444444");
    private static final UUID USER = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final UUID REPORT = UUID.fromString("55555555-5555-5555-5555-555555555555");

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Mock private ResearchJobService jobService;
    @Mock private ReportRepository reports;
    @Mock private ReportSectionRepository reportSections;
    @Mock private ResearchSourceRepository sources;
    @Mock private ClaimRepository claims;
    @Mock private ClaimEvidenceRepository claimEvidence;
    @Mock private EvidenceRepository evidence;

    private ReportService service;

    @BeforeEach
    void setUp() {
        service = new ReportService(jobService, reports, reportSections, sources, claims, claimEvidence,
                evidence, new ReportSectionContentMapper());
    }

    private JsonNode json(String raw) {
        try {
            return objectMapper.readTree(raw);
        } catch (Exception ex) {
            throw new IllegalArgumentException(ex);
        }
    }

    private ResearchJob completedJob() {
        return TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.COMPLETED);
    }

    @Test
    void refusesWithConflictWhileTheJobIsStillRunning() {
        when(jobService.requireOwnedJob(JOB))
                .thenReturn(TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.RESEARCHING));

        assertThatThrownBy(() -> service.getReport(JOB))
                .isInstanceOf(ReportNotReadyException.class)
                .satisfies(ex -> {
                    ReportNotReadyException notReady = (ReportNotReadyException) ex;
                    assertThat(notReady.getErrorCode().httpStatus().value()).isEqualTo(409);
                    assertThat(notReady.getDetails()).containsEntry("status", "RESEARCHING");
                });
    }

    @Test
    void ownershipFailuresPropagateAsNotFound() {
        when(jobService.requireOwnedJob(JOB)).thenThrow(ApiException.notFound("Research job was not found"));

        assertThatThrownBy(() -> service.getReport(JOB))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.NOT_FOUND);
    }

    @Test
    void reportsMissingStoredReportAsNotFound() {
        when(jobService.requireOwnedJob(JOB)).thenReturn(completedJob());
        when(reports.findByResearchJobId(JOB)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getReport(JOB))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.NOT_FOUND);
    }

    @Test
    void assemblesTheFullReportFromSectionsSourcesAndClaims() {
        UUID sourceId = UUID.randomUUID();
        UUID supportingEvidenceId = UUID.randomUUID();
        UUID contradictingEvidenceId = UUID.randomUUID();
        UUID claimId = UUID.randomUUID();

        when(jobService.requireOwnedJob(JOB)).thenReturn(completedJob());

        Report report = new Report(JOB);
        report.setId(REPORT);
        report.setOverallScore(new BigDecimal("82"));
        report.setVerdict("Recommended with caveats");
        report.setConfidence(new BigDecimal("0.74"));
        report.setExecutiveSummary("A strong all-rounder.");
        when(reports.findByResearchJobId(JOB)).thenReturn(Optional.of(report));

        when(reportSections.findByReportIdOrderByOrderIndexAscCreatedAtAsc(REPORT)).thenReturn(List.of(
                new ReportSection(REPORT, ReportSectionType.CATEGORY_ANALYSIS, "Categories",
                        json("[{\"category\": \"Sound Quality\", \"score\": 88, \"confidence\": 0.8}]"), 0),
                new ReportSection(REPORT, ReportSectionType.STRENGTHS, "Strengths",
                        json("[{\"text\": \"Best-in-class ANC\", \"evidenceIds\": [\"%s\"]}]"
                                .formatted(supportingEvidenceId)), 1),
                new ReportSection(REPORT, ReportSectionType.CONFLICTS, "Conflicts",
                        json("""
                                [{"topic": "Microphone quality",
                                  "positionA": {"text": "Good indoors"},
                                  "positionB": {"text": "Poor outdoors"},
                                  "explanation": "Wind noise.",
                                  "resolved": false}]"""), 2),
                new ReportSection(REPORT, ReportSectionType.CAVEATS, "Caveats",
                        json("[\"YouTube research was unavailable for this run\"]"), 3)));

        when(sources.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB))
                .thenReturn(List.of(TestFixtures.source(sourceId, JOB, "https://example.test/review")));

        Claim claim = TestFixtures.claim(claimId, JOB, "Noise cancelling",
                "ANC is best in class", ClaimStatus.CONTESTED);
        when(claims.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of(claim));
        when(claimEvidence.findByClaimIdIn(List.of(claimId))).thenReturn(List.of(
                new ClaimEvidence(claimId, supportingEvidenceId, EvidenceRelationship.SUPPORTS),
                new ClaimEvidence(claimId, contradictingEvidenceId, EvidenceRelationship.CONTRADICTS)));
        when(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of(
                TestFixtures.evidence(supportingEvidenceId, JOB, sourceId, "Noise cancelling", "ANC is superb"),
                TestFixtures.evidence(contradictingEvidenceId, JOB, sourceId, "Noise cancelling",
                        "ANC struggles with wind")));

        ReportDto dto = service.getReport(JOB);

        assertThat(dto.researchJobId()).isEqualTo(JOB);
        assertThat(dto.demoMode()).isTrue();
        assertThat(dto.overallScore()).isEqualByComparingTo("82");
        assertThat(dto.executiveSummary()).isEqualTo("A strong all-rounder.");
        assertThat(dto.categoryScores()).singleElement()
                .satisfies(score -> assertThat(score.category()).isEqualTo("Sound Quality"));
        assertThat(dto.keyStrengths()).singleElement()
                .satisfies(item -> assertThat(item.evidenceIds()).containsExactly(supportingEvidenceId));
        assertThat(dto.caveats()).containsExactly("YouTube research was unavailable for this run");
        assertThat(dto.sources()).singleElement()
                .satisfies(source -> assertThat(source.url()).isEqualTo("https://example.test/review"));

        assertThat(dto.conflicts()).singleElement().satisfies(conflict -> {
            assertThat(conflict.positionA().text()).isEqualTo("Good indoors");
            assertThat(conflict.positionB().text()).isEqualTo("Poor outdoors");
            assertThat(conflict.resolved()).isFalse();
        });

        assertThat(dto.claims()).singleElement().satisfies(reportClaim -> {
            assertThat(reportClaim.status()).isEqualTo(ClaimStatus.CONTESTED);
            assertThat(reportClaim.supportingEvidence()).singleElement()
                    .satisfies(item -> assertThat(item.text()).isEqualTo("ANC is superb"));
            assertThat(reportClaim.contradictingEvidence()).singleElement()
                    .satisfies(item -> assertThat(item.text()).isEqualTo("ANC struggles with wind"));
        });
    }

    @Test
    void servesAPartiallyCompletedJobsReport() {
        ResearchJob job = TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.PARTIALLY_COMPLETED);
        when(jobService.requireOwnedJob(JOB)).thenReturn(job);
        Report report = new Report(JOB);
        report.setId(REPORT);
        when(reports.findByResearchJobId(JOB)).thenReturn(Optional.of(report));
        when(reportSections.findByReportIdOrderByOrderIndexAscCreatedAtAsc(REPORT)).thenReturn(List.of());
        when(sources.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of());
        when(claims.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of());

        ReportDto dto = service.getReport(JOB);

        assertThat(dto.claims()).isEmpty();
        assertThat(dto.keyStrengths()).isEmpty();
    }
}
