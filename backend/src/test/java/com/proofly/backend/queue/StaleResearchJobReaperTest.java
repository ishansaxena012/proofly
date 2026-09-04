package com.proofly.backend.queue;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.proofly.backend.TestFixtures;
import com.proofly.backend.client.AiServiceClient;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.repository.ResearchJobRepository;
import com.proofly.backend.service.ResearchJobService;
import java.time.OffsetDateTime;
import java.util.List;
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
class StaleResearchJobReaperTest {

    private static final UUID USER = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Mock private ResearchJobRepository jobs;
    @Mock private ResearchJobService jobService;
    @Mock private AiServiceClient aiServiceClient;

    private StaleResearchJobReaper reaper;

    @BeforeEach
    void setUp() {
        // TestFixtures uses a 600s budget.
        reaper = new StaleResearchJobReaper(jobs, jobService, aiServiceClient, TestFixtures.properties());
    }

    private ResearchJob liveJob(ResearchJobStatus status, OffsetDateTime startedAt) {
        ResearchJob job = TestFixtures.job(UUID.randomUUID(), USER, UUID.randomUUID(), status);
        job.setStartedAt(startedAt);
        job.setCreatedAt(startedAt);
        return job;
    }

    @Test
    void failsAJobThatHasOutrunItsDurationBudget() {
        ResearchJob stale = liveJob(ResearchJobStatus.RESEARCHING, OffsetDateTime.now().minusHours(2));
        when(jobs.findByStatusIn(any())).thenReturn(List.of(stale));

        assertThat(reaper.reap()).isEqualTo(1);

        verify(jobService).fail(eq(stale.getId()), eq("TIMEOUT"), any());
        verify(aiServiceClient).cancel(stale.getId());
    }

    @Test
    void leavesAJobStillInsideItsBudgetAlone() {
        ResearchJob fresh = liveJob(ResearchJobStatus.RESEARCHING, OffsetDateTime.now().minusSeconds(30));
        when(jobs.findByStatusIn(any())).thenReturn(List.of(fresh));

        assertThat(reaper.reap()).isZero();

        verify(jobService, never()).fail(any(), any(), any());
        verify(aiServiceClient, never()).cancel(any());
    }

    @Test
    void fallsBackToCreatedAtForAJobThatWasNeverDispatched() {
        ResearchJob neverStarted =
                TestFixtures.job(UUID.randomUUID(), USER, UUID.randomUUID(), ResearchJobStatus.QUEUED);
        neverStarted.setStartedAt(null);
        neverStarted.setCreatedAt(OffsetDateTime.now().minusHours(2));
        when(jobs.findByStatusIn(any())).thenReturn(List.of(neverStarted));

        assertThat(reaper.reap()).isEqualTo(1);

        verify(jobService).fail(eq(neverStarted.getId()), eq("TIMEOUT"), any());
    }

    @Test
    void onlyEverConsidersLiveStatuses() {
        when(jobs.findByStatusIn(any())).thenReturn(List.of());

        reaper.reap();

        org.mockito.ArgumentCaptor<List<ResearchJobStatus>> statuses =
                org.mockito.ArgumentCaptor.forClass(List.class);
        verify(jobs).findByStatusIn(statuses.capture());
        assertThat(statuses.getValue())
                .contains(ResearchJobStatus.QUEUED, ResearchJobStatus.RUNNING, ResearchJobStatus.RESEARCHING)
                .doesNotContain(ResearchJobStatus.COMPLETED, ResearchJobStatus.FAILED,
                        ResearchJobStatus.PARTIALLY_COMPLETED, ResearchJobStatus.CANCELLED);
    }

    @Test
    void oneUnreapableJobDoesNotStopTheSweep() {
        ResearchJob broken = liveJob(ResearchJobStatus.RUNNING, OffsetDateTime.now().minusHours(2));
        ResearchJob other = liveJob(ResearchJobStatus.VERIFYING, OffsetDateTime.now().minusHours(2));
        when(jobs.findByStatusIn(any())).thenReturn(List.of(broken, other));
        doThrow(new IllegalStateException("database down"))
                .when(jobService).fail(eq(broken.getId()), any(), any());

        assertThat(reaper.reap()).isEqualTo(1);

        verify(jobService).fail(eq(other.getId()), eq("TIMEOUT"), any());
    }

    @Test
    void theScheduledEntryPointSwallowsFailures() {
        when(jobs.findByStatusIn(any())).thenThrow(new IllegalStateException("database down"));

        reaper.reapStaleJobs();

        verify(jobService, never()).fail(any(), any(), any());
    }
}
