package com.proofly.backend.api.dto;

import com.proofly.backend.domain.ResearchSource;
import com.proofly.backend.domain.SourceChannel;
import com.proofly.backend.domain.SourceStatus;
import com.proofly.backend.domain.SourceType;
import java.math.BigDecimal;
import java.util.UUID;

/** {@code GET /api/v1/research/{id}/sources} element. */
public record SourceDto(
        UUID id,
        SourceChannel channel,
        String url,
        String title,
        SourceType sourceType,
        BigDecimal authorityScore,
        Boolean firstHand,
        UUID independenceGroupId,
        SourceStatus status) {

    public static SourceDto from(ResearchSource source) {
        return new SourceDto(
                source.getId(),
                source.getChannel(),
                source.getUrl(),
                source.getTitle(),
                source.getSourceType(),
                source.getAuthorityScore(),
                source.getFirstHand(),
                source.getIndependenceGroupId(),
                source.getStatus());
    }
}
