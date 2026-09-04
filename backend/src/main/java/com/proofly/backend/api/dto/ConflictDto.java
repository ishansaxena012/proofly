package com.proofly.backend.api.dto;

/**
 * A preserved contradiction: both positions survive with their own evidence, and
 * {@code resolved} says whether the pipeline could explain the disagreement away
 * (e.g. context-dependence) rather than whether one side "won".
 */
public record ConflictDto(
        String topic,
        EvidenceBackedTextDto positionA,
        EvidenceBackedTextDto positionB,
        String explanation,
        boolean resolved) {
}
