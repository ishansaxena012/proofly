package com.proofly.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.proofly.backend.api.dto.CategoryScoreDto;
import com.proofly.backend.api.dto.ConflictDto;
import com.proofly.backend.api.dto.EvidenceBackedTextDto;
import com.proofly.backend.api.dto.KeyFindingDto;
import com.proofly.backend.api.dto.ReportClaimDto;
import com.proofly.backend.api.dto.ReportDto;
import com.proofly.backend.api.dto.ReportSourceDto;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ReportNotReadyException;
import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimEvidence;
import com.proofly.backend.domain.Evidence;
import com.proofly.backend.domain.EvidenceRelationship;
import com.proofly.backend.domain.Report;
import com.proofly.backend.domain.ReportSection;
import com.proofly.backend.domain.ReportSectionType;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.repository.ClaimEvidenceRepository;
import com.proofly.backend.repository.ClaimRepository;
import com.proofly.backend.repository.EvidenceRepository;
import com.proofly.backend.repository.ReportRepository;
import com.proofly.backend.repository.ReportSectionRepository;
import com.proofly.backend.repository.ResearchSourceRepository;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Assembles the flagship report DTO from the normalised tables.
 *
 * <p>Sources and claims are read from {@code research_sources}/{@code claims} rather than
 * from the report JSON, so every citation in the response is a row that really exists and
 * really belongs to this job.
 */
@Service
public class ReportService {

    private final ResearchJobService jobService;
    private final ReportRepository reports;
    private final ReportSectionRepository reportSections;
    private final ResearchSourceRepository sources;
    private final ClaimRepository claims;
    private final ClaimEvidenceRepository claimEvidence;
    private final EvidenceRepository evidence;
    private final ReportSectionContentMapper contentMapper;

    public ReportService(ResearchJobService jobService,
                         ReportRepository reports,
                         ReportSectionRepository reportSections,
                         ResearchSourceRepository sources,
                         ClaimRepository claims,
                         ClaimEvidenceRepository claimEvidence,
                         EvidenceRepository evidence,
                         ReportSectionContentMapper contentMapper) {
        this.jobService = jobService;
        this.reports = reports;
        this.reportSections = reportSections;
        this.sources = sources;
        this.claims = claims;
        this.claimEvidence = claimEvidence;
        this.evidence = evidence;
        this.contentMapper = contentMapper;
    }

    @Transactional(readOnly = true)
    public ReportDto getReport(UUID researchJobId) {
        ResearchJob job = jobService.requireOwnedJob(researchJobId);
        if (!job.getStatus().isReportAvailable()) {
            throw new ReportNotReadyException(job.getStatus());
        }
        Report report = reports.findByResearchJobId(researchJobId)
                .orElseThrow(() -> ApiException.notFound(
                        "No report has been stored for research job " + researchJobId));

        Map<ReportSectionType, JsonNode> byType = new EnumMap<>(ReportSectionType.class);
        for (ReportSection section : reportSections.findByReportIdOrderByOrderIndexAscCreatedAtAsc(report.getId())) {
            byType.putIfAbsent(section.getSectionType(), section.getContent());
        }

        String executiveSummary = report.getExecutiveSummary() != null
                ? report.getExecutiveSummary()
                : contentMapper.plainText(byType.get(ReportSectionType.EXECUTIVE_SUMMARY));

        List<CategoryScoreDto> categoryScores =
                contentMapper.categoryScores(byType.get(ReportSectionType.CATEGORY_ANALYSIS));
        List<EvidenceBackedTextDto> strengths =
                contentMapper.evidenceBackedList(byType.get(ReportSectionType.STRENGTHS));
        List<EvidenceBackedTextDto> weaknesses =
                contentMapper.evidenceBackedList(byType.get(ReportSectionType.WEAKNESSES));
        List<KeyFindingDto> keyFindings =
                contentMapper.keyFindings(byType.get(ReportSectionType.KEY_FINDINGS));
        List<EvidenceBackedTextDto> praise =
                contentMapper.evidenceBackedList(byType.get(ReportSectionType.COMMON_PRAISE));
        List<EvidenceBackedTextDto> complaints =
                contentMapper.evidenceBackedList(byType.get(ReportSectionType.COMMON_COMPLAINTS));
        List<ConflictDto> conflicts =
                contentMapper.conflicts(byType.get(ReportSectionType.CONFLICTS));
        EvidenceBackedTextDto longTermOwnership =
                contentMapper.singleEvidenceBacked(byType.get(ReportSectionType.LONG_TERM_OWNERSHIP));
        List<String> whoShouldBuy = contentMapper.stringList(byType.get(ReportSectionType.WHO_SHOULD_BUY));
        List<String> whoShouldAvoid = contentMapper.stringList(byType.get(ReportSectionType.WHO_SHOULD_AVOID));
        List<String> caveats = contentMapper.stringList(byType.get(ReportSectionType.CAVEATS));

        List<ReportSourceDto> sourceDtos = sources.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId)
                .stream()
                .map(ReportSourceDto::from)
                .toList();

        return new ReportDto(
                researchJobId,
                job.isDemoMode(),
                report.getOverallScore(),
                report.getVerdict(),
                report.getConfidence(),
                executiveSummary,
                categoryScores,
                strengths,
                weaknesses,
                keyFindings,
                praise,
                complaints,
                conflicts,
                longTermOwnership,
                whoShouldBuy,
                whoShouldAvoid,
                caveats,
                sourceDtos,
                buildClaims(researchJobId),
                report.getGeneratedAt(),
                report.getVersion());
    }

    /** Claims with their evidence split by relationship, so conflicts stay visible. */
    private List<ReportClaimDto> buildClaims(UUID researchJobId) {
        List<Claim> jobClaims = claims.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId);
        if (jobClaims.isEmpty()) {
            return List.of();
        }
        List<UUID> claimIds = jobClaims.stream().map(Claim::getId).toList();
        List<ClaimEvidence> links = claimEvidence.findByClaimIdIn(claimIds);

        Map<UUID, Evidence> evidenceById = new HashMap<>();
        for (Evidence row : evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId)) {
            evidenceById.put(row.getId(), row);
        }

        Map<UUID, List<ClaimEvidence>> linksByClaim = new HashMap<>();
        for (ClaimEvidence link : links) {
            linksByClaim.computeIfAbsent(link.getClaimId(), key -> new ArrayList<>()).add(link);
        }

        List<ReportClaimDto> result = new ArrayList<>(jobClaims.size());
        for (Claim claim : jobClaims) {
            List<ClaimEvidence> claimLinks = linksByClaim.getOrDefault(claim.getId(), List.of());
            result.add(new ReportClaimDto(
                    claim.getId(),
                    claim.getTopic(),
                    claim.getStatement(),
                    claim.getStatus(),
                    claim.getConfidence(),
                    excerpts(claimLinks, EvidenceRelationship.SUPPORTS, evidenceById),
                    excerpts(claimLinks, EvidenceRelationship.CONTRADICTS, evidenceById),
                    excerpts(claimLinks, EvidenceRelationship.CONTEXTUALIZES, evidenceById)));
        }
        return List.copyOf(result);
    }

    private static List<ReportClaimDto.ClaimEvidenceDto> excerpts(List<ClaimEvidence> links,
                                                                 EvidenceRelationship relationship,
                                                                 Map<UUID, Evidence> evidenceById) {
        List<ReportClaimDto.ClaimEvidenceDto> result = new ArrayList<>();
        for (ClaimEvidence link : links) {
            if (link.getRelationship() != relationship) {
                continue;
            }
            Evidence row = evidenceById.get(link.getEvidenceId());
            if (row != null) {
                result.add(new ReportClaimDto.ClaimEvidenceDto(row.getId(), row.getText(), row.getSourceId()));
            }
        }
        return List.copyOf(result);
    }
}
