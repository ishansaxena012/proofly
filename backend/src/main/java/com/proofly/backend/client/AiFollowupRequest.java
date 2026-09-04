package com.proofly.backend.client;

import com.proofly.backend.api.dto.EvidenceDto;
import java.util.List;

/**
 * Body of {@code POST {AI_SERVICE_URL}/internal/v1/research/{id}/followup}.
 *
 * <p>The backend ships the job's already-persisted evidence and claims with the question so
 * the AI service answers strictly from what was actually gathered, and cannot introduce new
 * unsupported facts.
 */
public record AiFollowupRequest(String question, List<EvidenceDto> evidence, List<AiClaimContext> claims) {
}
