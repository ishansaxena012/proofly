package com.proofly.backend.client;

import java.util.List;
import java.util.UUID;

/** Response of the AI service follow-up endpoint. */
public record AiFollowupResponse(String answer, List<UUID> citedEvidenceIds) {
}
