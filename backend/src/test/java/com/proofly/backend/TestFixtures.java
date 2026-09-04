package com.proofly.backend;

import com.proofly.backend.config.ProoflyProperties;
import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimStatus;
import com.proofly.backend.domain.Evidence;
import com.proofly.backend.domain.EvidenceType;
import com.proofly.backend.domain.Product;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.domain.ResearchSource;
import com.proofly.backend.domain.SourceChannel;
import com.proofly.backend.security.ProoflyPrincipal;
import java.math.BigDecimal;
import java.time.Duration;
import java.util.UUID;

/** Shared builders so tests describe intent rather than boilerplate. */
public final class TestFixtures {

    public static final String INTERNAL_KEY = "test-internal-key";

    private TestFixtures() {
    }

    public static ProoflyProperties properties() {
        return properties(3);
    }

    public static ProoflyProperties properties(int maxConcurrentJobs) {
        return new ProoflyProperties(
                new ProoflyProperties.Ai("http://ai-service.test", Duration.ofSeconds(1),
                        Duration.ofSeconds(2), Duration.ofSeconds(5), 3, Duration.ofMillis(1)),
                new ProoflyProperties.Research(maxConcurrentJobs, true, "proofly:research:queue",
                        "proofly:events:", Duration.ofSeconds(60), Duration.ofSeconds(20),
                        Duration.ofSeconds(600)),
                new ProoflyProperties.Security(INTERNAL_KEY, "", "", "dev.proofly.local"));
    }

    public static ProoflyPrincipal principal(UUID userId) {
        return new ProoflyPrincipal(userId, userId + "@dev.proofly.local", true);
    }

    public static Product product(UUID id, String rawQuery) {
        Product product = new Product(rawQuery);
        product.setId(id);
        return product;
    }

    public static ResearchJob job(UUID id, UUID userId, UUID productId, ResearchJobStatus status) {
        ResearchJob job = new ResearchJob(userId, productId, true);
        job.setId(id);
        job.setStatus(status);
        job.setCurrentStage(status.name());
        return job;
    }

    public static ResearchSource source(UUID id, UUID jobId, String url) {
        ResearchSource source = new ResearchSource(jobId, SourceChannel.WEB, url);
        source.setId(id);
        source.setTitle("Title for " + url);
        return source;
    }

    public static Evidence evidence(UUID id, UUID jobId, UUID sourceId, String topic, String text) {
        Evidence evidence = new Evidence(jobId, sourceId, topic, EvidenceType.CUSTOMER_EXPERIENCE, text);
        evidence.setId(id);
        return evidence;
    }

    public static Claim claim(UUID id, UUID jobId, String topic, String statement, ClaimStatus status) {
        Claim claim = new Claim(jobId, topic, statement, status);
        claim.setId(id);
        claim.setConfidence(new BigDecimal("0.80"));
        return claim;
    }
}
