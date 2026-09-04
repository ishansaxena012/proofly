package com.proofly.backend.client;

import java.util.UUID;

/** Body of {@code POST {AI_SERVICE_URL}/internal/v1/research/execute}. */
public record ExecuteResearchCommand(UUID researchJobId, String productQuery, boolean demoMode) {
}
