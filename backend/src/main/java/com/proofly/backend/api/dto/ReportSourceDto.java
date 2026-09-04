package com.proofly.backend.api.dto;

import com.proofly.backend.domain.ResearchSource;
import com.proofly.backend.domain.SourceChannel;
import com.proofly.backend.domain.SourceType;
import java.util.UUID;

public record ReportSourceDto(
        UUID id,
        String url,
        String title,
        SourceType sourceType,
        SourceChannel channel) {

    public static ReportSourceDto from(ResearchSource source) {
        return new ReportSourceDto(source.getId(), source.getUrl(), source.getTitle(),
                source.getSourceType(), source.getChannel());
    }
}
