package com.proofly.backend.queue;

import com.proofly.backend.client.AiServiceClient;
import com.proofly.backend.config.ProoflyProperties;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.repository.ResearchJobRepository;
import com.proofly.backend.service.ResearchJobService;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Fails jobs that have outrun {@code RESEARCH_MAX_DURATION_SECONDS}.
 *
 * <p>The AI service enforces its own duration budget, but if it dies mid-run nothing would
 * otherwise move the job out of a live state, and a job stuck in {@code RESEARCHING}
 * forever holds an SSE stream open and tells the user a lie. This is the backstop: once a
 * job is past its budget it is marked {@code FAILED}/{@code TIMEOUT}, and a best-effort
 * cancel is sent to the AI service so it stops spending on a job nobody is waiting for.
 */
@Component
public class StaleResearchJobReaper {

    private static final Logger log = LoggerFactory.getLogger(StaleResearchJobReaper.class);

    private static final List<ResearchJobStatus> LIVE_STATUSES = Arrays.stream(ResearchJobStatus.values())
            .filter(status -> !status.isTerminal())
            .toList();

    private final ResearchJobRepository jobs;
    private final ResearchJobService jobService;
    private final AiServiceClient aiServiceClient;
    private final ProoflyProperties properties;

    public StaleResearchJobReaper(ResearchJobRepository jobs,
                                  ResearchJobService jobService,
                                  AiServiceClient aiServiceClient,
                                  ProoflyProperties properties) {
        this.jobs = jobs;
        this.jobService = jobService;
        this.aiServiceClient = aiServiceClient;
        this.properties = properties;
    }

    // Deliberately not transactional: each fail() opens its own write transaction, so a
    // read-only wrapper here would make them fail, and one bad job would not roll back the
    // rest of the sweep.
    @Scheduled(fixedDelayString = "${proofly-dispatcher.reaper-interval-ms:30000}")
    public void reapStaleJobs() {
        try {
            reap();
        } catch (RuntimeException ex) {
            log.error("Stale job sweep failed; the loop stays alive", ex);
        }
    }

    /** Visible for testing; never throws for an individual job. */
    public int reap() {
        Duration budget = properties.research().maxDuration();
        if (budget == null || budget.isZero() || budget.isNegative()) {
            return 0;
        }
        OffsetDateTime cutoff = OffsetDateTime.now().minus(budget);
        int reaped = 0;

        for (ResearchJob job : jobs.findByStatusIn(LIVE_STATUSES)) {
            OffsetDateTime startedAt = job.getStartedAt() != null ? job.getStartedAt() : job.getCreatedAt();
            if (startedAt == null || startedAt.isAfter(cutoff)) {
                continue;
            }
            log.warn("Research job {} exceeded its {}s budget in status {}; failing it",
                    job.getId(), budget.toSeconds(), job.getStatus());
            try {
                jobService.fail(job.getId(), "TIMEOUT",
                        "Research exceeded the maximum duration of " + budget.toSeconds() + " seconds");
                aiServiceClient.cancel(job.getId());
                reaped++;
            } catch (RuntimeException ex) {
                log.error("Could not fail timed-out research job {}", job.getId(), ex);
            }
        }
        return reaped;
    }
}
