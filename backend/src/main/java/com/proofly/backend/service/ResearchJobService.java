package com.proofly.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.api.dto.CreateResearchRequest;
import com.proofly.backend.api.dto.CreateResearchResponse;
import com.proofly.backend.api.dto.EvidenceDto;
import com.proofly.backend.api.dto.ResearchJobDto;
import com.proofly.backend.api.dto.SourceDto;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.config.ProoflyProperties;
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
import com.proofly.backend.security.ProoflyPrincipal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/**
 * Owns the {@code research_jobs} lifecycle and every ownership decision on it.
 *
 * <p>Public read paths go through {@link #requireOwnedJob(UUID)}, which resolves a job by
 * id <em>and</em> the authenticated user id, and reports a job owned by somebody else as
 * {@code 404} so the API never leaks which job ids exist.
 */
@Service
public class ResearchJobService {

    private static final Logger log = LoggerFactory.getLogger(ResearchJobService.class);

    private final ResearchJobRepository jobs;
    private final ProductRepository products;
    private final ResearchSourceRepository sources;
    private final EvidenceRepository evidence;
    private final ResearchJobQueue queue;
    private final ResearchEventService eventService;
    private final ResearchJobStateMachine stateMachine;
    private final UserProvisioningService userProvisioning;
    private final CurrentUserProvider currentUser;
    private final ProoflyProperties properties;
    private final ObjectMapper objectMapper;

    public ResearchJobService(ResearchJobRepository jobs,
                              ProductRepository products,
                              ResearchSourceRepository sources,
                              EvidenceRepository evidence,
                              ResearchJobQueue queue,
                              ResearchEventService eventService,
                              ResearchJobStateMachine stateMachine,
                              UserProvisioningService userProvisioning,
                              CurrentUserProvider currentUser,
                              ProoflyProperties properties,
                              ObjectMapper objectMapper) {
        this.jobs = jobs;
        this.products = products;
        this.sources = sources;
        this.evidence = evidence;
        this.queue = queue;
        this.eventService = eventService;
        this.stateMachine = stateMachine;
        this.userProvisioning = userProvisioning;
        this.currentUser = currentUser;
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    // ── create ───────────────────────────────────────────────────────────────

    /**
     * Persists {@code products} + {@code research_jobs}, moves the job {@code CREATED →
     * QUEUED} and hands it to the Redis queue. The queue push happens after commit so the
     * dispatcher can never pick up a job id that is not yet readable.
     */
    @Transactional
    public CreateResearchResponse createResearchJob(CreateResearchRequest request) {
        ProoflyPrincipal principal = currentUser.requirePrincipal();
        userProvisioning.ensureUser(principal);

        String productQuery = request.productQuery() == null ? "" : request.productQuery().trim();
        if (productQuery.isEmpty()) {
            throw ApiException.validation("productQuery must not be blank");
        }

        boolean demoMode = request.demoMode() != null
                ? request.demoMode()
                : properties.research().demoMode();

        Product product = products.save(new Product(productQuery));
        ResearchJob job = jobs.save(new ResearchJob(principal.userId(), product.getId(), demoMode));

        applyStatus(job, ResearchJobStatus.QUEUED, ResearchJobStatus.QUEUED.name());
        jobs.save(job);

        UUID jobId = job.getId();
        enqueueAfterCommit(jobId);
        log.info("Created research job {} for user {} (demoMode={})", jobId, principal.userId(), demoMode);
        return new CreateResearchResponse(jobId, job.getStatus());
    }

    // ── ownership-scoped reads ───────────────────────────────────────────────

    @Transactional(readOnly = true)
    public ResearchJobDto getResearchJob(UUID researchJobId) {
        ResearchJob job = requireOwnedJob(researchJobId);
        Product product = job.getProductId() == null ? null : products.findById(job.getProductId()).orElse(null);
        return ResearchJobDto.from(job, product);
    }

    @Transactional(readOnly = true)
    public List<SourceDto> getSources(UUID researchJobId) {
        requireOwnedJob(researchJobId);
        return sources.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId).stream()
                .map(SourceDto::from)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<EvidenceDto> getEvidence(UUID researchJobId, String topic) {
        requireOwnedJob(researchJobId);
        var rows = (topic == null || topic.isBlank())
                ? evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(researchJobId)
                : evidence.findByResearchJobIdAndTopicIgnoreCaseOrderByCreatedAtAscIdAsc(researchJobId, topic.trim());
        return rows.stream().map(EvidenceDto::from).toList();
    }

    /**
     * Resolves a job the current user owns, or throws {@code 404}. This is the single
     * choke point for ownership on the public API.
     */
    @Transactional(readOnly = true)
    public ResearchJob requireOwnedJob(UUID researchJobId) {
        UUID userId = currentUser.requireUserId();
        return jobs.findByIdAndUserId(researchJobId, userId)
                .orElseThrow(() -> ApiException.notFound("Research job " + researchJobId + " was not found"));
    }

    /** Unscoped lookup for internal (service-to-service) callers only. */
    @Transactional(readOnly = true)
    public ResearchJob requireJob(UUID researchJobId) {
        return jobs.findById(researchJobId)
                .orElseThrow(() -> ApiException.notFound("Research job " + researchJobId + " was not found"));
    }

    // ── lifecycle ────────────────────────────────────────────────────────────

    /** Applies a validated status transition and mirrors it into {@code research_events}. */
    @Transactional
    public ResearchJob transition(UUID researchJobId,
                                  ResearchJobStatus target,
                                  String currentStage,
                                  String errorCode,
                                  String errorMessage) {
        ResearchJob job = requireJob(researchJobId);
        ResearchJobStatus previous = job.getStatus();
        stateMachine.requireTransition(previous, target);

        applyStatus(job, target, currentStage);
        if (errorCode != null) {
            job.setErrorCode(errorCode);
        }
        if (errorMessage != null) {
            job.setErrorMessage(errorMessage);
        }
        jobs.save(job);

        if (previous != target) {
            eventService.record(researchJobId, eventTypeFor(target), describe(previous, target, errorMessage),
                    statusPayload(previous, job));
        }
        return job;
    }

    /** Terminal failure path used by the dispatcher and by internal error callbacks. */
    @Transactional
    public ResearchJob fail(UUID researchJobId, String errorCode, String errorMessage) {
        return transition(researchJobId, ResearchJobStatus.FAILED, ResearchJobStatus.FAILED.name(),
                errorCode, errorMessage);
    }

    @Transactional(readOnly = true)
    public Optional<Product> findProduct(UUID productId) {
        return productId == null ? Optional.empty() : products.findById(productId);
    }

    private void applyStatus(ResearchJob job, ResearchJobStatus target, String currentStage) {
        job.setStatus(target);
        job.setCurrentStage(currentStage == null ? target.name() : currentStage);
        if (target == ResearchJobStatus.RUNNING && job.getStartedAt() == null) {
            job.setStartedAt(OffsetDateTime.now());
        }
        if (target.isTerminal() && job.getCompletedAt() == null) {
            job.setCompletedAt(OffsetDateTime.now());
        }
    }

    private void enqueueAfterCommit(UUID researchJobId) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    queue.enqueue(researchJobId);
                }
            });
        } else {
            queue.enqueue(researchJobId);
        }
    }

    private static ResearchEventType eventTypeFor(ResearchJobStatus status) {
        return switch (status) {
            case RESEARCHING -> ResearchEventType.RESEARCH_STARTED;
            case EXTRACTING_EVIDENCE -> ResearchEventType.EVIDENCE_EXTRACTION_STARTED;
            case VERIFYING -> ResearchEventType.VERIFICATION_STARTED;
            case GENERATING_REPORT -> ResearchEventType.REPORT_GENERATION_STARTED;
            case COMPLETED -> ResearchEventType.REPORT_COMPLETED;
            case PARTIALLY_COMPLETED -> ResearchEventType.JOB_PARTIALLY_COMPLETED;
            case FAILED, CANCELLED -> ResearchEventType.JOB_FAILED;
            default -> ResearchEventType.STATUS_CHANGED;
        };
    }

    private static String describe(ResearchJobStatus previous, ResearchJobStatus target, String errorMessage) {
        if (errorMessage != null && !errorMessage.isBlank()) {
            return errorMessage;
        }
        return "Research job moved from " + previous + " to " + target;
    }

    private JsonNode statusPayload(ResearchJobStatus previous, ResearchJob job) {
        return objectMapper.valueToTree(Map.of(
                "previousStatus", previous.name(),
                "status", job.getStatus().name(),
                "currentStage", job.getCurrentStage() == null ? job.getStatus().name() : job.getCurrentStage()));
    }
}
