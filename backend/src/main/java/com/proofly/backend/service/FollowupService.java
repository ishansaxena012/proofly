package com.proofly.backend.service;

import com.proofly.backend.api.dto.EvidenceDto;
import com.proofly.backend.api.dto.FollowupRequest;
import com.proofly.backend.api.dto.FollowupResponse;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.client.AiClaimContext;
import com.proofly.backend.client.AiFollowupRequest;
import com.proofly.backend.client.AiFollowupResponse;
import com.proofly.backend.client.AiServiceClient;
import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimEvidence;
import com.proofly.backend.domain.Evidence;
import com.proofly.backend.domain.EvidenceRelationship;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.repository.ClaimEvidenceRepository;
import com.proofly.backend.repository.ClaimRepository;
import com.proofly.backend.repository.EvidenceRepository;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Evidence-grounded follow-up Q&amp;A (docs/API.md §followup).
 *
 * <p>The backend, not the AI service, decides what evidence is in scope: it ships exactly
 * the job's persisted evidence and claims, and then drops any cited evidence id that is
 * not in that set. An answer can therefore only ever point at evidence this job actually
 * gathered.
 */
@Service
public class FollowupService {

    private static final Logger log = LoggerFactory.getLogger(FollowupService.class);

    private final ResearchJobService jobService;
    private final EvidenceRepository evidence;
    private final ClaimRepository claims;
    private final ClaimEvidenceRepository claimEvidence;
    private final AiServiceClient aiServiceClient;

    public FollowupService(ResearchJobService jobService,
                           EvidenceRepository evidence,
                           ClaimRepository claims,
                           ClaimEvidenceRepository claimEvidence,
                           AiServiceClient aiServiceClient) {
        this.jobService = jobService;
        this.evidence = evidence;
        this.claims = claims;
        this.claimEvidence = claimEvidence;
        this.aiServiceClient = aiServiceClient;
    }

    @Transactional(readOnly = true)
    public FollowupResponse ask(UUID researchJobId, FollowupRequest request) {
        ResearchJob job = jobService.requireOwnedJob(researchJobId);

        List<Evidence> jobEvidence = evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId);
        if (jobEvidence.isEmpty()) {
            throw new ApiException(ErrorCode.INSUFFICIENT_DATA,
                    "Research job " + researchJobId + " has no evidence to answer follow-up questions from");
        }

        List<EvidenceDto> evidenceContext = jobEvidence.stream().map(EvidenceDto::from).toList();
        Set<UUID> allowedEvidenceIds = new HashSet<>(jobEvidence.size());
        jobEvidence.forEach(row -> allowedEvidenceIds.add(row.getId()));

        AiFollowupRequest aiRequest =
                new AiFollowupRequest(request.question().trim(), evidenceContext, claimContext(researchJobId));
        AiFollowupResponse aiResponse = aiServiceClient.followup(researchJobId, aiRequest);

        List<UUID> cited = filterCitations(researchJobId, aiResponse.citedEvidenceIds(), allowedEvidenceIds);
        String answer = aiResponse.answer() == null ? "" : aiResponse.answer();
        log.debug("Answered follow-up for job {} ({}) citing {} evidence rows",
                researchJobId, job.getStatus(), cited.size());
        return new FollowupResponse(answer, cited);
    }

    private List<AiClaimContext> claimContext(UUID researchJobId) {
        List<Claim> jobClaims = claims.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId);
        if (jobClaims.isEmpty()) {
            return List.of();
        }
        List<ClaimEvidence> links = claimEvidence.findByClaimIdIn(jobClaims.stream().map(Claim::getId).toList());
        List<AiClaimContext> result = new ArrayList<>(jobClaims.size());
        for (Claim claim : jobClaims) {
            List<UUID> supporting = new ArrayList<>();
            List<UUID> contradicting = new ArrayList<>();
            for (ClaimEvidence link : links) {
                if (!link.getClaimId().equals(claim.getId())) {
                    continue;
                }
                if (link.getRelationship() == EvidenceRelationship.SUPPORTS) {
                    supporting.add(link.getEvidenceId());
                } else if (link.getRelationship() == EvidenceRelationship.CONTRADICTS) {
                    contradicting.add(link.getEvidenceId());
                }
            }
            result.add(AiClaimContext.of(claim, List.copyOf(supporting), List.copyOf(contradicting)));
        }
        return List.copyOf(result);
    }

    private List<UUID> filterCitations(UUID researchJobId, List<UUID> cited, Set<UUID> allowed) {
        if (cited == null || cited.isEmpty()) {
            return List.of();
        }
        Set<UUID> kept = new LinkedHashSet<>();
        for (UUID id : cited) {
            if (id != null && allowed.contains(id)) {
                kept.add(id);
            } else {
                log.warn("Dropping follow-up citation {} for job {}: not part of this job's evidence",
                        id, researchJobId);
            }
        }
        return List.copyOf(kept);
    }
}
