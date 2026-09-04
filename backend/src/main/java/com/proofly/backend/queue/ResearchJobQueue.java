package com.proofly.backend.queue;

import com.proofly.backend.config.ProoflyProperties;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * The Redis list backing the research job queue ({@code proofly:research:queue}).
 *
 * <p>Jobs are pushed on the right and popped from the left, so the queue is FIFO. Popping
 * is atomic, which is what lets several backend instances share one queue without handing
 * the same job to two dispatchers.
 */
@Component
public class ResearchJobQueue {

    private static final Logger log = LoggerFactory.getLogger(ResearchJobQueue.class);

    private final StringRedisTemplate redis;
    private final String queueKey;

    public ResearchJobQueue(StringRedisTemplate redis, ProoflyProperties properties) {
        this.redis = redis;
        this.queueKey = properties.research().queueKey();
    }

    public void enqueue(UUID researchJobId) {
        redis.opsForList().rightPush(queueKey, researchJobId.toString());
        log.debug("Enqueued research job {}", researchJobId);
    }

    /** Atomically claims the next queued job id, or empty when the queue is drained. */
    public Optional<UUID> dequeue() {
        String raw = redis.opsForList().leftPop(queueKey);
        if (raw == null) {
            return Optional.empty();
        }
        try {
            return Optional.of(UUID.fromString(raw));
        } catch (IllegalArgumentException ex) {
            log.warn("Discarding malformed research job id on {}: {}", queueKey, raw);
            return Optional.empty();
        }
    }

    public String queueKey() {
        return queueKey;
    }
}
