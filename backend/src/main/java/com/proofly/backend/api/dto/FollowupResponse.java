package com.proofly.backend.api.dto;

import java.util.List;
import java.util.UUID;

/** {@code POST /api/v1/research/{id}/followup} response. */
public record FollowupResponse(String answer, List<UUID> citedEvidenceIds) {
}
