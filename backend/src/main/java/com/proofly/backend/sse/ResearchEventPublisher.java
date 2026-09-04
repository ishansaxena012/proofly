package com.proofly.backend.sse;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.api.dto.ResearchEventDto;
import com.proofly.backend.config.ProoflyProperties;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * Fans a persisted research event out to every backend instance over Redis pub/sub on
 * {@code proofly:events:{jobId}}.
 *
 * <p>Publishing is best-effort by design: the durable copy is the {@code research_events}
 * row, and any subscriber that misses a live message still gets it from the replay that
 * every SSE stream starts with. A Redis outage must therefore never fail the write that
 * produced the event.
 */
@Component
public class ResearchEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(ResearchEventPublisher.class);

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final ProoflyProperties properties;

    public ResearchEventPublisher(StringRedisTemplate redis, ObjectMapper objectMapper,
                                  ProoflyProperties properties) {
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    public void publish(UUID researchJobId, ResearchEventDto event) {
        String channel = properties.research().eventChannel(researchJobId);
        try {
            redis.convertAndSend(channel, objectMapper.writeValueAsString(event));
        } catch (JsonProcessingException ex) {
            log.error("Could not serialise event {} for job {}", event.eventType(), researchJobId, ex);
        } catch (RuntimeException ex) {
            log.warn("Could not publish event {} for job {} to Redis ({}); SSE clients will pick it up on replay",
                    event.eventType(), researchJobId, ex.getMessage());
        }
    }
}
