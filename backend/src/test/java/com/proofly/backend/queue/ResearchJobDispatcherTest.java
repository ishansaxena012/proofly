package com.proofly.backend.queue;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.proofly.backend.TestFixtures;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.client.AiServiceClient;
import com.proofly.backend.client.AiServiceException;
import com.proofly.backend.client.ExecuteResearchCommand;
import com.proofly.backend.domain.Product;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.service.ResearchJobService;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
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
class ResearchJobDispatcherTest {

    private static final UUID JOB = UUID.fromString("99999999-9999-9999-9999-999999999999");
    private static final UUID USER = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final UUID PRODUCT = UUID.fromString("88888888-8888-8888-8888-888888888888");

    @Mock private ResearchJobQueue queue;
    @Mock private ResearchJobService jobService;
    @Mock private AiServiceClient aiServiceClient;

    private ExecutorService workers;
    private ResearchJobDispatcher dispatcher;
    private ResearchJob job;

    @BeforeEach
    void setUp() {
        workers = Executors.newSingleThreadExecutor();
        dispatcher = new ResearchJobDispatcher(queue, jobService, aiServiceClient,
                TestFixtures.properties(), workers);
        job = TestFixtures.job(JOB, USER, PRODUCT, ResearchJobStatus.QUEUED);
        when(jobService.requireJob(JOB)).thenReturn(job);
        when(jobService.findProduct(PRODUCT))
                .thenReturn(Optional.of(TestFixtures.product(PRODUCT, "Sony WH-1000XM6")));
    }

    @AfterEach
    void tearDown() throws InterruptedException {
        workers.shutdown();
        workers.awaitTermination(5, TimeUnit.SECONDS);
    }

    @Test
    void marksTheJobRunningAndHandsItToTheAiService() {
        dispatcher.dispatch(JOB);

        verify(jobService).transition(JOB, ResearchJobStatus.RUNNING, "RUNNING", null, null);
        ArgumentCaptor<ExecuteResearchCommand> command = ArgumentCaptor.forClass(ExecuteResearchCommand.class);
        verify(aiServiceClient).execute(command.capture());
        assertThat(command.getValue().researchJobId()).isEqualTo(JOB);
        assertThat(command.getValue().productQuery()).isEqualTo("Sony WH-1000XM6");
        assertThat(command.getValue().demoMode()).isTrue();
        verify(jobService, never()).fail(any(), any(), any());
    }

    @Test
    void retriesThenFailsTheJobWithAgentFailureWhenTheAiServiceIsDown() {
        doThrow(AiServiceException.unreachable("execute", new RuntimeException("connection refused")))
                .when(aiServiceClient).execute(any());

        dispatcher.dispatch(JOB);

        verify(aiServiceClient, times(3)).execute(any());
        verify(jobService).fail(eq(JOB), eq("AGENT_FAILURE"), any());
    }

    @Test
    void aFailureToRecordTheFailureStillDoesNotEscape() {
        doThrow(AiServiceException.unreachable("execute", new RuntimeException("down")))
                .when(aiServiceClient).execute(any());
        doThrow(new IllegalStateException("database down"))
                .when(jobService).fail(any(), any(), any());

        dispatcher.dispatch(JOB);

        verify(jobService).fail(eq(JOB), eq("AGENT_FAILURE"), any());
    }

    @Test
    void skipsJobsThatAreNoLongerQueued() {
        job.setStatus(ResearchJobStatus.RUNNING);

        dispatcher.dispatch(JOB);

        verify(aiServiceClient, never()).execute(any());
        verify(jobService, never()).transition(any(), any(), any(), any(), any());
    }

    @Test
    void dropsQueuedIdsWhoseJobHasVanished() {
        when(jobService.requireJob(JOB)).thenThrow(ApiException.notFound("gone"));

        dispatcher.dispatch(JOB);

        verify(aiServiceClient, never()).execute(any());
    }

    @Test
    void failsAJobThatSomehowHasNoProductQuery() {
        when(jobService.findProduct(PRODUCT)).thenReturn(Optional.of(new Product("   ")));

        dispatcher.dispatch(JOB);

        verify(jobService).fail(eq(JOB), eq("INVALID_PRODUCT"), any());
        verify(aiServiceClient, never()).execute(any());
    }

    @Test
    void pollDrainsTheQueueUpToTheConcurrencyLimit() throws Exception {
        UUID second = UUID.randomUUID();
        UUID third = UUID.randomUUID();
        when(queue.dequeue())
                .thenReturn(Optional.of(JOB), Optional.of(second), Optional.of(third), Optional.empty());
        for (UUID id : List.of(second, third)) {
            ResearchJob other = TestFixtures.job(id, USER, PRODUCT, ResearchJobStatus.QUEUED);
            when(jobService.requireJob(id)).thenReturn(other);
        }

        dispatcher.pollQueue();
        workers.shutdown();
        assertThat(workers.awaitTermination(5, TimeUnit.SECONDS)).isTrue();

        verify(aiServiceClient, times(3)).execute(any());
    }

    @Test
    void aBrokenQueueDoesNotKillThePollLoop() {
        when(queue.dequeue()).thenThrow(new IllegalStateException("redis is down"));

        dispatcher.pollQueue();
        dispatcher.pollQueue();

        verify(aiServiceClient, never()).execute(any());
    }

    @Test
    void pollStopsWhenTheQueueIsEmpty() {
        when(queue.dequeue()).thenReturn(Optional.empty());

        dispatcher.pollQueue();

        verify(queue, times(1)).dequeue();
        verify(aiServiceClient, never()).execute(any());
    }
}
