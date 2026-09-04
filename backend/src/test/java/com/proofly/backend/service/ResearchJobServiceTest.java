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
import com.proofly.backend.api.dto.CreateResearchRequest;
import com.proofly.backend.api.dto.CreateResearchResponse;
import com.proofly.backend.api.dto.EvidenceDto;
import com.proofly.backend.api.dto.ResearchJobDto;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.domain.Product;
import com.proofly.backend.domain.ResearchEventType;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.queue.ResearchJobQueue;
import com.proofly.backend.repository.EvidenceRepository;
import com.proofly.backend.repository.ProductRepository;
import com.proofly.backend.repository.ResearchJobRepository;
import com.proofly.backend.repository.ResearchSourceRepository;
import com.proofly.backend.security.CurrentUserProvider;
import java.util.List;
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
class ResearchJobServiceTest {

    private static final UUID USER = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final UUID OTHER_USER = UUID.fromString("22222222-2222-2222-2222-222222222222");
    private static final UUID JOB = UUID.fromString("33333333-3333-3333-3333-333333333333");

    @Mock private ResearchJobRepository jobs;
    @Mock private ProductRepository products;
    @Mock private ResearchSourceRepository sources;
    @Mock private EvidenceRepository evidence;
    @Mock private ResearchJobQueue queue;
    @Mock private ResearchEventService eventService;
    @Mock private UserProvisioningService userProvisioning;
    @Mock private CurrentUserProvider currentUser;

    private ResearchJobService service;

    @BeforeEach
    void setUp() {
        service = new ResearchJobService(jobs, products, sources, evidence, queue, eventService,
                new ResearchJobStateMachine(), userProvisioning, currentUser,
                TestFixtures.properties(), new ObjectMapper());
        when(currentUser.requirePrincipal()).thenReturn(TestFixtures.principal(USER));
        when(currentUser.requireUserId()).thenReturn(USER);
        when(products.save(any(Product.class))).thenAnswer(call -> call.getArgument(0));
        when(jobs.save(any(ResearchJob.class))).thenAnswer(call -> call.getArgument(0));
    }

    @Test
    void createPersistsProductAndJobThenQueuesIt() {
        CreateResearchResponse response =
                service.createResearchJob(new CreateResearchRequest("  Sony WH-1000XM6  ", null));

        ArgumentCaptor<Product> product = ArgumentCaptor.forClass(Product.class);
        verify(products).save(product.capture());
        assertThat(product.getValue().getRawQuery()).isEqualTo("Sony WH-1000XM6");

        ArgumentCaptor<ResearchJob> job = ArgumentCaptor.forClass(ResearchJob.class);
        verify(jobs, org.mockito.Mockito.atLeastOnce()).save(job.capture());
        ResearchJob saved = job.getValue();
        assertThat(saved.getUserId()).isEqualTo(USER);
        assertThat(saved.getProductId()).isEqualTo(product.getValue().getId());
        assertThat(saved.getStatus()).isEqualTo(ResearchJobStatus.QUEUED);

        assertThat(response.status()).isEqualTo(ResearchJobStatus.QUEUED);
        verify(queue).enqueue(response.researchJobId());
        verify(userProvisioning).ensureUser(any());
    }

    @Test
    void createUsesTheServerDemoModeDefaultWhenTheClientDoesNotAskForOne() {
        service.createResearchJob(new CreateResearchRequest("Sony WH-1000XM6", null));

        ArgumentCaptor<ResearchJob> job = ArgumentCaptor.forClass(ResearchJob.class);
        verify(jobs, org.mockito.Mockito.atLeastOnce()).save(job.capture());
        assertThat(job.getValue().isDemoMode()).isTrue();
    }

    @Test
    void createRejectsAWhitespaceOnlyQuery() {
        assertThatThrownBy(() -> service.createResearchJob(new CreateResearchRequest("   ", null)))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.VALIDATION_ERROR);
        verify(queue, never()).enqueue(any());
    }

    @Test
    void readingAJobResolvesItsProduct() {
        ResearchJob job = TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.RESEARCHING);
        when(jobs.findByIdAndUserId(JOB, USER)).thenReturn(Optional.of(job));
        when(products.findById(job.getProductId()))
                .thenReturn(Optional.of(TestFixtures.product(job.getProductId(), "Sony WH-1000XM6")));

        ResearchJobDto dto = service.getResearchJob(JOB);

        assertThat(dto.id()).isEqualTo(JOB);
        assertThat(dto.status()).isEqualTo(ResearchJobStatus.RESEARCHING);
        assertThat(dto.product().rawQuery()).isEqualTo("Sony WH-1000XM6");
    }

    @Test
    void aJobOwnedBySomebodyElseLooksLikeItDoesNotExist() {
        when(currentUser.requireUserId()).thenReturn(OTHER_USER);
        when(jobs.findByIdAndUserId(JOB, OTHER_USER)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getResearchJob(JOB))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.NOT_FOUND);
    }

    @Test
    void sourcesAndEvidenceAreOwnershipScopedToo() {
        when(jobs.findByIdAndUserId(JOB, USER)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getSources(JOB)).isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> service.getEvidence(JOB, null)).isInstanceOf(ApiException.class);
        verify(sources, never()).findByResearchJobIdOrderByCreatedAtAscIdAsc(any());
        verify(evidence, never()).findByResearchJobIdOrderByCreatedAtAscIdAsc(any());
    }

    @Test
    void evidenceCanBeFilteredByTopic() {
        ResearchJob job = TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.COMPLETED);
        when(jobs.findByIdAndUserId(JOB, USER)).thenReturn(Optional.of(job));
        UUID sourceId = UUID.randomUUID();
        when(evidence.findByResearchJobIdAndTopicIgnoreCaseOrderByCreatedAtAscIdAsc(JOB, "Battery"))
                .thenReturn(List.of(TestFixtures.evidence(UUID.randomUUID(), JOB, sourceId, "Battery", "40h")));

        List<EvidenceDto> filtered = service.getEvidence(JOB, "  Battery  ");

        assertThat(filtered).singleElement()
                .satisfies(dto -> assertThat(dto.topic()).isEqualTo("Battery"));
        verify(evidence, never()).findByResearchJobIdOrderByCreatedAtAscIdAsc(any());
    }

    @Test
    void transitionRecordsAnEventAndStampsStartedAt() {
        ResearchJob job = TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.QUEUED);
        when(jobs.findById(JOB)).thenReturn(Optional.of(job));

        service.transition(JOB, ResearchJobStatus.RUNNING, "RUNNING", null, null);

        assertThat(job.getStatus()).isEqualTo(ResearchJobStatus.RUNNING);
        assertThat(job.getStartedAt()).isNotNull();
        verify(eventService).record(eq(JOB), any(ResearchEventType.class), any(), any());
    }

    @Test
    void failingAJobStampsCompletedAtAndTheErrorCode() {
        ResearchJob job = TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.RUNNING);
        when(jobs.findById(JOB)).thenReturn(Optional.of(job));

        service.fail(JOB, "AGENT_FAILURE", "AI service is unreachable");

        assertThat(job.getStatus()).isEqualTo(ResearchJobStatus.FAILED);
        assertThat(job.getErrorCode()).isEqualTo("AGENT_FAILURE");
        assertThat(job.getErrorMessage()).isEqualTo("AI service is unreachable");
        assertThat(job.getCompletedAt()).isNotNull();
        verify(eventService).record(eq(JOB), eq(ResearchEventType.JOB_FAILED), any(), any());
    }

    @Test
    void aTerminalJobCannotBeRestarted() {
        ResearchJob job = TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.COMPLETED);
        when(jobs.findById(JOB)).thenReturn(Optional.of(job));

        assertThatThrownBy(() -> service.transition(JOB, ResearchJobStatus.RUNNING, null, null, null))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.VALIDATION_ERROR);
    }
}
