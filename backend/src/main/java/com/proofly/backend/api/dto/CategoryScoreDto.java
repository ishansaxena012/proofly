package com.proofly.backend.api.dto;

import java.math.BigDecimal;

public record CategoryScoreDto(String category, BigDecimal score, BigDecimal confidence) {
}
