package com.proofly.backend.queue;

import com.proofly.backend.client.AiServiceClient;
import com.proofly.backend.client.ExecuteResearchCommand;
import com.proofly.backend.config.ProoflyProperties;
import com.proofly.backend.domain.Product;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.service.ResearchJobService;
import jakarta.annotation.PreDestroy;
import java.time.Duration;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Drains {@code proofly:research:queue} and hands each job to the AI service.
 *
 * <p>Concurrency is bounded by {@code RESEARCH_MAX_CONCURRENT_JOBS}: a permit is held for
 * the whole dispatch attempt, so the backend never has more research runs in flight than
 * configured. A job that cannot be handed over — because the AI service is down — is
 * marked {@code FAILED} with {@code AGENT_FAILURE} after the configured number of
 * attempts. The poll loop itself catches everything, so no single bad job can stop the
 * dispatcher.
 */
@Component
public class ResearchJobDispatcher {

    private static final Logger log = LoggerFactory.getLogger(ResearchJobDispatcher.class);

    private final ResearchJobQueue queue;
    private final ResearchJobService jobService;
    private final AiServiceClient aiServiceClient;
    private final ProoflyProperties properties;
    private final Semaphore slots;
    private final ExecutorService workers;

    @org.springframework.beans.factory.annotation.Autowired
    public ResearchJobDispatcher(ResearchJobQueue queue,
                                 ResearchJobService jobService,
                                 AiServiceClient aiServiceClient,
                                 ProoflyProperties properties) {
        this(queue, jobService, aiServiceClient, properties, Executors.newVirtualThreadPerTaskExecutor());
    }

    ResearchJobDispatcher(ResearchJobQueue queue,
                          ResearchJobService jobService,
                          AiServiceClient aiServiceClient,
                          ProoflyProperties properties,
                          ExecutorService workers) {
        this.queue = queue;
        this.jobService = jobService;
        this.aiServiceClient = aiServiceClient;
        this.properties = properties;
        this.slots = new Semaphore(Math.max(1, properties.research().maxConcurrentJobs()));
        this.workers = workers;
    }

    /** Scheduled poll: claim as many queued jobs as there are free concurrency slots. */
    @Scheduled(fixedDelayString = "${proofly-dispatcher.poll-interval-ms:1000}")
    public void pollQueue() {
        try {
            int claimed = 0;
            while (slots.tryAcquire()) {
                Optional<UUID> next;
                try {
                    next = queue.dequeue();
                } catch (RuntimeException ex) {
                    slots.release();
                    log.warn("Could not read the research queue ({}); will retry on the next poll",
                            ex.getMessage());
                    return;
                }
                if (next.isEmpty()) {
                    slots.release();
                    break;
                }
                UUID researchJobId = next.get();
                claimed++;
                workers.execute(() -> {
                    try {
                        dispatch(researchJobId);
                    } finally {
                        slots.release();
                    }
                });
            }
            if (claimed > 0) {
                log.debug("Dispatcher claimed {} job(s) from {}", claimed, queue.queueKey());
            }
        } catch (RuntimeException ex) {
            log.error("Dispatcher poll failed; the loop stays alive", ex);
        }
    }

    /**
     * Hands one job to the AI service. Visible for testing and safe to call directly: it
     * never throws, and it is a no-op for jobs that are no longer queued.
     */
    public void dispatch(UUID researchJobId) {
        ResearchJob job;
        try {
            job = jobService.requireJob(researchJobId);
        } catch (RuntimeException ex) {
            log.warn("Dropping queued research job {}: {}", researchJobId, ex.getMessage());
            return;
        }

        if (job.getStatus() != ResearchJobStatus.QUEUED) {
            log.info("Skipping research job {} — already in status {}", researchJobId, job.getStatus());
            return;
        }

        String productQuery = jobService.findProduct(job.getProductId())
                .map(Product::getRawQuery)
                .orElse(null);
        if (productQuery == null || productQuery.isBlank()) {
            jobService.fail(researchJobId, "INVALID_PRODUCT", "Research job has no product query to research");
            return;
        }

        jobService.transition(researchJobId, ResearchJobStatus.RUNNING, ResearchJobStatus.RUNNING.name(), null, null);

        ExecuteResearchCommand command =
                new ExecuteResearchCommand(researchJobId, productQuery, job.isDemoMode());
        int attempts = Math.max(1, properties.ai().maxDispatchAttempts());
        RuntimeException lastFailure = null;

        for (int attempt = 1; attempt <= attempts; attempt++) {
            try {
                aiServiceClient.execute(command);
                return;
            } catch (RuntimeException ex) {
                lastFailure = ex;
                log.warn("Dispatch attempt {}/{} for job {} failed: {}",
                        attempt, attempts, researchJobId, ex.getMessage());
                if (attempt < attempts) {
                    sleepBackoff(attempt);
                }
            }
        }

        String message = lastFailure == null
                ? "AI service could not be reached"
                : lastFailure.getMessage();
        log.error("Giving up on research job {} after {} dispatch attempts", researchJobId, attempts);
        try {
            jobService.fail(researchJobId, "AGENT_FAILURE", message);
        } catch (RuntimeException ex) {
            log.error("Could not mark research job {} as FAILED", researchJobId, ex);
        }
    }

    private void sleepBackoff(int attempt) {
        Duration base = properties.ai().dispatchRetryBackoff();
        long millis = (base == null ? Duration.ofSeconds(2) : base).toMillis() * attempt;
        try {
            TimeUnit.MILLISECONDS.sleep(millis);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }

    @PreDestroy
    public void shutdown() {
        workers.shutdown();
    }
}
