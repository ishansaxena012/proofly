package com.proofly.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.proofly.backend.api.dto.CategoryScoreDto;
import com.proofly.backend.api.dto.ConflictDto;
import com.proofly.backend.api.dto.EvidenceBackedTextDto;
import com.proofly.backend.api.dto.KeyFindingDto;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Turns the free-form {@code report_sections.content} JSON written by the AI service into
 * the typed report DTO fields.
 *
 * <p>It is deliberately forgiving about the outer wrapper (a bare array, {@code {"items":
 * [...]}} or a single object all work) but never invents content: anything it cannot read
 * is dropped rather than guessed at, so nothing unsupported reaches the report.
 */
@Component
public class ReportSectionContentMapper {

    private static final Logger log = LoggerFactory.getLogger(ReportSectionContentMapper.class);

    public List<EvidenceBackedTextDto> evidenceBackedList(JsonNode content) {
        List<EvidenceBackedTextDto> result = new ArrayList<>();
        for (JsonNode item : items(content)) {
            EvidenceBackedTextDto dto = evidenceBacked(item);
            if (dto != null) {
                result.add(dto);
            }
        }
        return List.copyOf(result);
    }

    public EvidenceBackedTextDto singleEvidenceBacked(JsonNode content) {
        if (content == null || content.isNull()) {
            return null;
        }
        if (content.isArray()) {
            List<EvidenceBackedTextDto> list = evidenceBackedList(content);
            return list.isEmpty() ? null : list.get(0);
        }
        return evidenceBacked(content);
    }

    public List<String> stringList(JsonNode content) {
        List<String> result = new ArrayList<>();
        for (JsonNode item : items(content)) {
            if (item.isTextual()) {
                result.add(item.asText());
            } else if (item.isObject()) {
                String text = text(item, "text", "statement", "summary", "title");
                if (text != null) {
                    result.add(text);
                }
            }
        }
        return List.copyOf(result);
    }

    public List<CategoryScoreDto> categoryScores(JsonNode content) {
        List<CategoryScoreDto> result = new ArrayList<>();
        for (JsonNode item : items(content)) {
            if (!item.isObject()) {
                continue;
            }
            String category = text(item, "category", "name", "dimension");
            if (category == null) {
                continue;
            }
            result.add(new CategoryScoreDto(category, decimal(item, "score"), decimal(item, "confidence")));
        }
        return List.copyOf(result);
    }

    public List<KeyFindingDto> keyFindings(JsonNode content) {
        List<KeyFindingDto> result = new ArrayList<>();
        for (JsonNode item : items(content)) {
            if (item.isTextual()) {
                result.add(new KeyFindingDto(item.asText(), null));
                continue;
            }
            String text = text(item, "text", "statement", "finding");
            if (text != null) {
                result.add(new KeyFindingDto(text, uuid(item.get("claimId"))));
            }
        }
        return List.copyOf(result);
    }

    public List<ConflictDto> conflicts(JsonNode content) {
        List<ConflictDto> result = new ArrayList<>();
        for (JsonNode item : items(content)) {
            if (!item.isObject()) {
                continue;
            }
            EvidenceBackedTextDto positionA = evidenceBacked(item.get("positionA"));
            EvidenceBackedTextDto positionB = evidenceBacked(item.get("positionB"));
            if (positionA == null && positionB == null) {
                continue;
            }
            result.add(new ConflictDto(
                    text(item, "topic"),
                    positionA,
                    positionB,
                    text(item, "explanation", "reason"),
                    item.path("resolved").asBoolean(false)));
        }
        return List.copyOf(result);
    }

    /** Reads a section written as a single string (e.g. an executive summary). */
    public String plainText(JsonNode content) {
        if (content == null || content.isNull()) {
            return null;
        }
        if (content.isTextual()) {
            return content.asText();
        }
        return text(content, "text", "summary", "content");
    }

    // ── internals ────────────────────────────────────────────────────────────

    private EvidenceBackedTextDto evidenceBacked(JsonNode item) {
        if (item == null || item.isNull()) {
            return null;
        }
        if (item.isTextual()) {
            return new EvidenceBackedTextDto(item.asText(), List.of());
        }
        if (!item.isObject()) {
            return null;
        }
        String text = text(item, "text", "statement", "summary");
        if (text == null) {
            return null;
        }
        return new EvidenceBackedTextDto(text, uuidList(item.get("evidenceIds")));
    }

    /**
     * Normalises the section wrapper: a bare array, {@code {"items": [...]}} and a lone
     * object all iterate as a list of entries.
     */
    private Iterable<JsonNode> items(JsonNode content) {
        if (content == null || content.isNull()) {
            return List.of();
        }
        if (content.isArray()) {
            return content;
        }
        if (content.isObject()) {
            for (String wrapper : new String[]{"items", "entries", "values"}) {
                JsonNode nested = content.get(wrapper);
                if (nested != null && nested.isArray()) {
                    return nested;
                }
            }
            // A single-key object whose only value is an array is also a valid wrapper.
            if (content.size() == 1) {
                Iterator<JsonNode> only = content.elements();
                JsonNode value = only.next();
                if (value.isArray()) {
                    return value;
                }
            }
            return List.of(content);
        }
        if (content.isTextual()) {
            return List.of(content);
        }
        return List.of();
    }

    private static String text(JsonNode node, String... fields) {
        for (String field : fields) {
            JsonNode value = node.get(field);
            if (value != null && value.isTextual() && !value.asText().isBlank()) {
                return value.asText();
            }
        }
        return null;
    }

    private static BigDecimal decimal(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || !value.isNumber()) {
            return null;
        }
        return value.decimalValue();
    }

    private static List<UUID> uuidList(JsonNode node) {
        if (node == null || !node.isArray()) {
            return List.of();
        }
        List<UUID> ids = new ArrayList<>(((ArrayNode) node).size());
        for (JsonNode element : node) {
            UUID id = uuid(element);
            if (id != null) {
                ids.add(id);
            }
        }
        return List.copyOf(ids);
    }

    private static UUID uuid(JsonNode node) {
        if (node == null || !node.isTextual()) {
            return null;
        }
        try {
            return UUID.fromString(node.asText());
        } catch (IllegalArgumentException ex) {
            log.debug("Ignoring non-UUID id in report section content: {}", node.asText());
            return null;
        }
    }
}
