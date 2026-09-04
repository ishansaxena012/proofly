package com.proofly.backend.api.dto;

import com.proofly.backend.domain.ResearchJobStatus;
import java.util.UUID;

/** {@code 202} body for {@code POST /api/v1/research}. */
public record CreateResearchResponse(UUID researchJobId, ResearchJobStatus status) {
}
