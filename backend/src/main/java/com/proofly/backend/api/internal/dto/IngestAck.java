package com.proofly.backend.api.internal.dto;

import com.proofly.backend.domain.ResearchJobStatus;
import java.util.List;
import java.util.UUID;

/**
 * Uniform acknowledgement for internal callbacks.
 *
 * @param researchJobId the job the callback applied to
 * @param status        the job status after applying the callback
 * @param processed     how many rows the callback wrote
 * @param ids           ids of the written rows, in request order, so the AI service can
 *                      reference server-side ids (e.g. link evidence to a source) without
 *                      having to invent them
 */
public record IngestAck(UUID researchJobId, ResearchJobStatus status, int processed, List<UUID> ids) {

    public static IngestAck of(UUID researchJobId, ResearchJobStatus status, List<UUID> ids) {
        return new IngestAck(researchJobId, status, ids.size(), ids);
    }

    public static IngestAck ok(UUID researchJobId, ResearchJobStatus status) {
        return new IngestAck(researchJobId, status, 1, List.of());
    }
}
