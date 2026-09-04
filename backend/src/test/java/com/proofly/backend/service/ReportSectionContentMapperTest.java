package com.proofly.backend.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.api.dto.EvidenceBackedTextDto;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ReportSectionContentMapperTest {

    private static final UUID EVIDENCE_A = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private static final UUID EVIDENCE_B = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ReportSectionContentMapper mapper = new ReportSectionContentMapper();

    private JsonNode json(String raw) {
        try {
            return objectMapper.readTree(raw);
        } catch (Exception ex) {
            throw new IllegalArgumentException(ex);
        }
    }

    @Test
    void readsABareArrayOfEvidenceBackedItems() {
        var result = mapper.evidenceBackedList(json("""
                [{"text": "Excellent noise cancelling", "evidenceIds": ["%s", "%s"]}]
                """.formatted(EVIDENCE_A, EVIDENCE_B)));

        assertThat(result).singleElement().satisfies(item -> {
            assertThat(item.text()).isEqualTo("Excellent noise cancelling");
            assertThat(item.evidenceIds()).containsExactly(EVIDENCE_A, EVIDENCE_B);
        });
    }

    @Test
    void readsAnItemsWrapper() {
        var result = mapper.evidenceBackedList(json("""
                {"items": [{"text": "Comfortable over long sessions"}]}
                """));

        assertThat(result).singleElement()
                .extracting(EvidenceBackedTextDto::text)
                .isEqualTo("Comfortable over long sessions");
    }

    @Test
    void dropsEntriesWithNoReadableText() {
        var result = mapper.evidenceBackedList(json("""
                [{"evidenceIds": ["%s"]}, {"text": "Kept"}]
                """.formatted(EVIDENCE_A)));

        assertThat(result).extracting(EvidenceBackedTextDto::text).containsExactly("Kept");
    }

    @Test
    void ignoresCitationsThatAreNotUuids() {
        var result = mapper.evidenceBackedList(json("""
                [{"text": "Loud", "evidenceIds": ["not-a-uuid", "%s"]}]
                """.formatted(EVIDENCE_B)));

        assertThat(result.get(0).evidenceIds()).containsExactly(EVIDENCE_B);
    }

    @Test
    void readsCategoryScores() {
        var result = mapper.categoryScores(json("""
                [{"category": "Sound Quality", "score": 88, "confidence": 0.8},
                 {"score": 10}]
                """));

        assertThat(result).singleElement().satisfies(score -> {
            assertThat(score.category()).isEqualTo("Sound Quality");
            assertThat(score.score()).isEqualByComparingTo("88");
            assertThat(score.confidence()).isEqualByComparingTo("0.8");
        });
    }

    @Test
    void readsKeyFindingsWithAndWithoutClaimIds() {
        var result = mapper.keyFindings(json("""
                [{"text": "Battery beats the spec sheet", "claimId": "%s"}, "Plain string finding"]
                """.formatted(EVIDENCE_A)));

        assertThat(result).hasSize(2);
        assertThat(result.get(0).claimId()).isEqualTo(EVIDENCE_A);
        assertThat(result.get(1).text()).isEqualTo("Plain string finding");
        assertThat(result.get(1).claimId()).isNull();
    }

    @Test
    void preservesBothSidesOfAConflict() {
        var result = mapper.conflicts(json("""
                [{"topic": "Microphone quality",
                  "positionA": {"text": "Good indoors", "evidenceIds": ["%s"]},
                  "positionB": {"text": "Poor outdoors", "evidenceIds": ["%s"]},
                  "explanation": "Context-dependent.",
                  "resolved": false}]
                """.formatted(EVIDENCE_A, EVIDENCE_B)));

        assertThat(result).singleElement().satisfies(conflict -> {
            assertThat(conflict.topic()).isEqualTo("Microphone quality");
            assertThat(conflict.positionA().evidenceIds()).containsExactly(EVIDENCE_A);
            assertThat(conflict.positionB().evidenceIds()).containsExactly(EVIDENCE_B);
            assertThat(conflict.resolved()).isFalse();
        });
    }

    @Test
    void dropsAConflictWithNoPositions() {
        assertThat(mapper.conflicts(json("""
                [{"topic": "Nothing here"}]
                """))).isEmpty();
    }

    @Test
    void readsStringListsFromStringsAndObjects() {
        assertThat(mapper.stringList(json("""
                ["Commuters", {"text": "Frequent flyers"}, 42]
                """))).containsExactly("Commuters", "Frequent flyers");
    }

    @Test
    void readsASingleObjectSection() {
        EvidenceBackedTextDto ownership = mapper.singleEvidenceBacked(json("""
                {"text": "Earpads wear after 18 months", "evidenceIds": ["%s"]}
                """.formatted(EVIDENCE_A)));

        assertThat(ownership).isNotNull();
        assertThat(ownership.evidenceIds()).containsExactly(EVIDENCE_A);
    }

    @Test
    void handlesMissingSectionsWithoutInventingContent() {
        assertThat(mapper.evidenceBackedList(null)).isEmpty();
        assertThat(mapper.stringList(null)).isEmpty();
        assertThat(mapper.categoryScores(null)).isEmpty();
        assertThat(mapper.keyFindings(null)).isEmpty();
        assertThat(mapper.conflicts(null)).isEmpty();
        assertThat(mapper.singleEvidenceBacked(null)).isNull();
        assertThat(mapper.plainText(null)).isNull();
    }

    @Test
    void readsPlainTextSections() {
        assertThat(mapper.plainText(json("\"A short summary\""))).isEqualTo("A short summary");
        assertThat(mapper.plainText(json("{\"summary\": \"Wrapped summary\"}"))).isEqualTo("Wrapped summary");
    }
}
