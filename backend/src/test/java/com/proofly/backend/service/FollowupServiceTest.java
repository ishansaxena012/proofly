package com.proofly.backend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.proofly.backend.TestFixtures;
import com.proofly.backend.api.dto.FollowupRequest;
import com.proofly.backend.api.dto.FollowupResponse;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.client.AiFollowupRequest;
import com.proofly.backend.client.AiFollowupResponse;
import com.proofly.backend.client.AiServiceClient;
import com.proofly.backend.client.AiServiceException;
import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimEvidence;
import com.proofly.backend.domain.ClaimStatus;
import com.proofly.backend.domain.Evidence;
import com.proofly.backend.domain.EvidenceRelationship;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.repository.ClaimEvidenceRepository;
import com.proofly.backend.repository.ClaimRepository;
import com.proofly.backend.repository.EvidenceRepository;
import java.util.ArrayList;
import java.util.List;
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
class FollowupServiceTest {

    private static final UUID JOB = UUID.fromString("66666666-6666-6666-6666-666666666666");
    private static final UUID USER = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Mock private ResearchJobService jobService;
    @Mock private EvidenceRepository evidence;
    @Mock private ClaimRepository claims;
    @Mock private ClaimEvidenceRepository claimEvidence;
    @Mock private AiServiceClient aiServiceClient;

    private FollowupService service;
    private UUID evidenceId;

    @BeforeEach
    void setUp() {
        service = new FollowupService(jobService, evidence, claims, claimEvidence, aiServiceClient);
        evidenceId = UUID.randomUUID();
        when(jobService.requireOwnedJob(JOB))
                .thenReturn(TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.COMPLETED));
        Evidence row = TestFixtures.evidence(evidenceId, JOB, UUID.randomUUID(), "Battery", "Lasts 38 hours");
        List<Evidence> rows = new ArrayList<>();
        rows.add(row);
        when(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(rows);
        when(claims.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of());
    }

    @Test
    void sendsTheJobsEvidenceAndClaimsToTheAiService() {
        UUID claimId = UUID.randomUUID();
        Claim claim = TestFixtures.claim(claimId, JOB, "Battery", "Battery exceeds spec", ClaimStatus.SUPPORTED);
        when(claims.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of(claim));
        when(claimEvidence.findByClaimIdIn(List.of(claimId))).thenReturn(List.of(
                new ClaimEvidence(claimId, evidenceId, EvidenceRelationship.SUPPORTS)));
        when(aiServiceClient.followup(eq(JOB), any()))
                .thenReturn(new AiFollowupResponse("About 38 hours.", List.of(evidenceId)));

        FollowupResponse response = service.ask(JOB, new FollowupRequest("  How is battery life?  "));

        ArgumentCaptor<AiFollowupRequest> sent = ArgumentCaptor.forClass(AiFollowupRequest.class);
        verify(aiServiceClient).followup(eq(JOB), sent.capture());
        assertThat(sent.getValue().question()).isEqualTo("How is battery life?");
        assertThat(sent.getValue().evidence()).singleElement()
                .satisfies(item -> assertThat(item.id()).isEqualTo(evidenceId));
        assertThat(sent.getValue().claims()).singleElement().satisfies(context -> {
            assertThat(context.id()).isEqualTo(claimId);
            assertThat(context.supportingEvidenceIds()).containsExactly(evidenceId);
        });
        assertThat(response.answer()).isEqualTo("About 38 hours.");
        assertThat(response.citedEvidenceIds()).containsExactly(evidenceId);
    }

    @Test
    void dropsCitationsThatAreNotThisJobsEvidence() {
        UUID foreignEvidence = UUID.randomUUID();
        when(aiServiceClient.followup(eq(JOB), any()))
                .thenReturn(new AiFollowupResponse("Answer", List.of(foreignEvidence, evidenceId, evidenceId)));

        FollowupResponse response = service.ask(JOB, new FollowupRequest("How is battery life?"));

        assertThat(response.citedEvidenceIds()).containsExactly(evidenceId);
    }

    @Test
    void refusesWhenNoEvidenceWasEverGathered() {
        when(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(JOB)).thenReturn(List.of());

        assertThatThrownBy(() -> service.ask(JOB, new FollowupRequest("How is battery life?")))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.INSUFFICIENT_DATA);
        verify(aiServiceClient, never()).followup(any(), any());
    }

    @Test
    void neverCallsTheAiServiceForAJobTheCallerDoesNotOwn() {
        when(jobService.requireOwnedJob(JOB)).thenThrow(ApiException.notFound("Research job was not found"));

        assertThatThrownBy(() -> service.ask(JOB, new FollowupRequest("How is battery life?")))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.NOT_FOUND);
        verify(aiServiceClient, never()).followup(any(), any());
    }

    @Test
    void surfacesAnUnreachableAiServiceAsAgentFailure() {
        when(aiServiceClient.followup(eq(JOB), any()))
                .thenThrow(AiServiceException.unreachable("followup", new RuntimeException("connection refused")));

        assertThatThrownBy(() -> service.ask(JOB, new FollowupRequest("How is battery life?")))
                .isInstanceOf(AiServiceException.class)
                .extracting(ex -> ((AiServiceException) ex).getErrorCode())
                .isEqualTo(ErrorCode.AGENT_FAILURE);
    }
}
