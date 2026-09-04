package com.proofly.backend.api.dto;

import java.util.List;
import java.util.UUID;

/** A narrative statement plus the evidence ids it is traceable to. */
public record EvidenceBackedTextDto(String text, List<UUID> evidenceIds) {
}
