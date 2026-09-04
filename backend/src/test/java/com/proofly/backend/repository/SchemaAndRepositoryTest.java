package com.proofly.backend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.domain.Claim;
import com.proofly.backend.domain.ClaimEvidence;
import com.proofly.backend.domain.ClaimStatus;
import com.proofly.backend.domain.Evidence;
import com.proofly.backend.domain.EvidenceRelationship;
import com.proofly.backend.domain.EvidenceStrength;
import com.proofly.backend.domain.EvidenceType;
import com.proofly.backend.domain.Passage;
import com.proofly.backend.domain.Product;
import com.proofly.backend.domain.Report;
import com.proofly.backend.domain.ReportSection;
import com.proofly.backend.domain.ReportSectionType;
import com.proofly.backend.domain.ResearchEvent;
import com.proofly.backend.domain.ResearchEventType;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.domain.ResearchSource;
import com.proofly.backend.domain.Sentiment;
import com.proofly.backend.domain.SourceChannel;
import com.proofly.backend.domain.SourceDocument;
import com.proofly.backend.domain.SourceStatus;
import com.proofly.backend.domain.SourceType;
import com.proofly.backend.domain.UserAccount;
import jakarta.persistence.EntityManager;
import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

/**
 * Exercises the Flyway schema and every repository against a real Postgres with pgvector,
 * because the parts most likely to break — the {@code jsonb} columns, the {@code vector}
 * extension, the quoted {@code position} column and the ownership-scoped query — have no
 * meaningful equivalent on an in-memory database.
 *
 * <p>The class is skipped rather than failed when Docker is unavailable, so the rest of
 * the suite still runs on machines without it.
 */
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Testcontainers(disabledWithoutDocker = true)
class SchemaAndRepositoryTest {

    @Container
    @SuppressWarnings("resource")
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"))
            .withDatabaseName("proofly")
            .withUsername("postgres")
            .withPassword("postgres");

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("spring.flyway.enabled", () -> "true");
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "none");
    }

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Autowired private EntityManager entityManager;
    @Autowired private UserAccountRepository users;
    @Autowired private ProductRepository products;
    @Autowired private ResearchJobRepository jobs;
    @Autowired private ResearchEventRepository events;
    @Autowired private ResearchSourceRepository sources;
    @Autowired private SourceDocumentRepository documents;
    @Autowired private PassageRepository passages;
    @Autowired private EvidenceRepository evidence;
    @Autowired private ClaimRepository claims;
    @Autowired private ClaimEvidenceRepository claimEvidence;
    @Autowired private ReportRepository reports;
    @Autowired private ReportSectionRepository reportSections;

    private UUID ownerId;
    private UUID otherUserId;
    private ResearchJob job;

    @BeforeEach
    void seed() {
        ownerId = users.save(new UserAccount(null, "owner-" + UUID.randomUUID() + "@dev.proofly.local", "Owner"))
                .getId();
        otherUserId = users.save(new UserAccount(null, "other-" + UUID.randomUUID() + "@dev.proofly.local", null))
                .getId();
        Product product = products.save(new Product("Sony WH-1000XM6"));
        job = jobs.save(new ResearchJob(ownerId, product.getId(), true));
    }

    @Test
    void theMigrationsCreateEveryTableAndTheVectorExtension() {
        Object extension = entityManager
                .createNativeQuery("select count(*) from pg_extension where extname = 'vector'")
                .getSingleResult();
        assertThat(((Number) extension).intValue()).isEqualTo(1);

        Object tables = entityManager.createNativeQuery("""
                        select count(*) from information_schema.tables
                        where table_schema = 'public' and table_name in
                        ('users','products','research_jobs','research_events','research_sources',
                         'documents','passages','evidence','claims','claim_evidence','reports','report_sections')
                        """)
                .getSingleResult();
        assertThat(((Number) tables).intValue()).isEqualTo(12);
    }

    @Test
    void theEmbeddingColumnIsARealVectorWithAnAnnIndex() {
        Object columnType = entityManager.createNativeQuery("""
                        select udt_name from information_schema.columns
                        where table_name = 'passages' and column_name = 'embedding'
                        """)
                .getSingleResult();
        assertThat(columnType.toString()).isEqualTo("vector");

        Object index = entityManager.createNativeQuery("""
                        select count(*) from pg_indexes
                        where tablename = 'passages' and indexname = 'idx_passages_embedding_hnsw'
                        """)
                .getSingleResult();
        assertThat(((Number) index).intValue()).isEqualTo(1);
    }

    @Test
    void aJobIsOnlyVisibleToItsOwner() {
        assertThat(jobs.findByIdAndUserId(job.getId(), ownerId)).isPresent();
        assertThat(jobs.findByIdAndUserId(job.getId(), otherUserId)).isEmpty();
    }

    @Test
    void researchEventsRoundTripTheirJsonbPayloadInOrder() {
        events.save(new ResearchEvent(job.getId(), ResearchEventType.PRODUCT_IDENTIFIED, "Identified",
                objectMapper.valueToTree(java.util.Map.of("brand", "Sony", "confidence", 0.95))));
        events.save(new ResearchEvent(job.getId(), ResearchEventType.RESEARCH_STARTED, "Started", null));
        entityManager.flush();
        entityManager.clear();

        List<ResearchEvent> log = events.findByResearchJobIdOrderByCreatedAtAscIdAsc(job.getId());

        assertThat(log).hasSize(2);
        assertThat(log.get(0).getPayload().get("brand").asText()).isEqualTo("Sony");
        assertThat(log.get(0).getPayload().get("confidence").asDouble()).isEqualTo(0.95);
        assertThat(log.get(1).getPayload()).isNull();
    }

    @Test
    void sourcesDocumentsAndPassagesPersistIncludingTheQuotedPositionColumn() {
        ResearchSource source = sources.save(newSource("https://example.test/review"));
        SourceDocument document = documents.save(new SourceDocument(source.getId(), "Full text", "hash-1", 120));
        passages.save(new Passage(document.getId(), "Chunk one", 0));
        passages.save(new Passage(document.getId(), "Chunk two", 1));
        entityManager.flush();
        entityManager.clear();

        assertThat(documents.findBySourceId(source.getId())).hasSize(1);
        assertThat(documents.findByContentHash("hash-1")).hasSize(1);
        List<Passage> stored = passages.findByDocumentIdOrderByPositionAsc(document.getId());
        assertThat(stored).extracting(Passage::getText).containsExactly("Chunk one", "Chunk two");
        assertThat(stored.get(0).getEmbedding()).isNull();
    }

    @Test
    void aSourceUrlIsUniqueWithinAJob() {
        sources.save(newSource("https://example.test/dup"));
        entityManager.flush();

        assertThat(sources.findByResearchJobIdAndUrl(job.getId(), "https://example.test/dup")).isPresent();
        assertThat(sources.countByResearchJobId(job.getId())).isEqualTo(1);
    }

    @Test
    void evidenceIsQueryableByTopic() {
        ResearchSource source = sources.save(newSource("https://example.test/evidence"));
        Evidence battery = new Evidence(job.getId(), source.getId(), "Battery",
                EvidenceType.MEASUREMENT, "38 hours measured");
        battery.setSentiment(Sentiment.POSITIVE);
        battery.setStrength(EvidenceStrength.STRONG);
        evidence.save(battery);
        evidence.save(new Evidence(job.getId(), source.getId(), "Comfort",
                EvidenceType.CUSTOMER_EXPERIENCE, "Comfortable for long flights"));
        entityManager.flush();
        entityManager.clear();

        assertThat(evidence.findByResearchJobIdOrderByCreatedAtAscIdAsc(job.getId())).hasSize(2);
        assertThat(evidence.findByResearchJobIdAndTopicIgnoreCaseOrderByCreatedAtAscIdAsc(job.getId(), "battery"))
                .singleElement()
                .satisfies(row -> assertThat(row.getStrength()).isEqualTo(EvidenceStrength.STRONG));
        assertThat(evidence.countByResearchJobId(job.getId())).isEqualTo(2);
    }

    @Test
    void claimsKeepBothSupportingAndContradictingEvidence() {
        ResearchSource source = sources.save(newSource("https://example.test/claims"));
        Evidence supporting = evidence.save(new Evidence(job.getId(), source.getId(), "Microphone",
                EvidenceType.EXPERT_OPINION, "Clear indoors"));
        Evidence contradicting = evidence.save(new Evidence(job.getId(), source.getId(), "Microphone",
                EvidenceType.CUSTOMER_EXPERIENCE, "Unusable in wind"));

        Claim claim = claims.save(new Claim(job.getId(), "Microphone", "Call quality is good",
                ClaimStatus.CONTESTED));
        claim.setConfidence(new BigDecimal("0.45"));
        claimEvidence.save(new ClaimEvidence(claim.getId(), supporting.getId(), EvidenceRelationship.SUPPORTS));
        claimEvidence.save(new ClaimEvidence(claim.getId(), contradicting.getId(),
                EvidenceRelationship.CONTRADICTS));
        entityManager.flush();
        entityManager.clear();

        assertThat(claims.countByResearchJobId(job.getId())).isEqualTo(1);
        assertThat(claims.countByResearchJobIdAndStatusIn(job.getId(),
                List.of(ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED))).isZero();
        assertThat(claimEvidence.findByClaimId(claim.getId()))
                .extracting(ClaimEvidence::getRelationship)
                .containsExactlyInAnyOrder(EvidenceRelationship.SUPPORTS, EvidenceRelationship.CONTRADICTS);
    }

    @Test
    void aReportAndItsJsonbSectionsPersistInOrder() {
        Report report = reports.save(new Report(job.getId()));
        report.setOverallScore(new BigDecimal("82"));
        report.setVerdict("Recommended with caveats");
        report.setConfidence(new BigDecimal("0.74"));
        report.setExecutiveSummary("Strong all-rounder.");

        reportSections.save(new ReportSection(report.getId(), ReportSectionType.STRENGTHS, "Strengths",
                objectMapper.valueToTree(List.of(java.util.Map.of("text", "Best-in-class ANC"))), 1));
        reportSections.save(new ReportSection(report.getId(), ReportSectionType.EXECUTIVE_SUMMARY, "Summary",
                objectMapper.valueToTree(java.util.Map.of("text", "Strong all-rounder.")), 0));
        entityManager.flush();
        entityManager.clear();

        Report stored = reports.findByResearchJobId(job.getId()).orElseThrow();
        assertThat(stored.getOverallScore()).isEqualByComparingTo("82");
        assertThat(stored.getVersion()).isEqualTo(1);

        List<ReportSection> sections =
                reportSections.findByReportIdOrderByOrderIndexAscCreatedAtAsc(stored.getId());
        assertThat(sections).extracting(ReportSection::getSectionType)
                .containsExactly(ReportSectionType.EXECUTIVE_SUMMARY, ReportSectionType.STRENGTHS);
        assertThat(sections.get(1).getContent().get(0).get("text").asText()).isEqualTo("Best-in-class ANC");
    }

    @Test
    void jobStatusAndCountersPersistThroughTheEnumMapping() {
        job.setStatus(ResearchJobStatus.PARTIALLY_COMPLETED);
        job.setCurrentStage("PARTIALLY_COMPLETED");
        job.setSourceCount(12);
        job.setEvidenceCount(34);
        job.setClaimCount(9);
        job.setVerifiedClaimCount(7);
        job.setErrorCode("SOURCE_FAILURE");
        jobs.save(job);
        entityManager.flush();
        entityManager.clear();

        ResearchJob stored = jobs.findById(job.getId()).orElseThrow();
        assertThat(stored.getStatus()).isEqualTo(ResearchJobStatus.PARTIALLY_COMPLETED);
        assertThat(stored.getVerifiedClaimCount()).isEqualTo(7);
        assertThat(stored.getErrorCode()).isEqualTo("SOURCE_FAILURE");
        assertThat(stored.getCreatedAt()).isNotNull();
        assertThat(stored.getUpdatedAt()).isNotNull();
        assertThat(jobs.findByStatusIn(List.of(ResearchJobStatus.PARTIALLY_COMPLETED)))
                .extracting(ResearchJob::getId)
                .contains(job.getId());
    }

    @Test
    void usersAreLookedUpCaseInsensitivelyByEmail() {
        UserAccount stored = users.findById(ownerId).orElseThrow();
        assertThat(users.findByEmailIgnoreCase(stored.getEmail().toUpperCase())).isPresent();
    }

    private ResearchSource newSource(String url) {
        ResearchSource source = new ResearchSource(job.getId(), SourceChannel.WEB, url);
        source.setTitle("A review");
        source.setSourceType(SourceType.PROFESSIONAL_REVIEW);
        source.setAuthorityScore(new BigDecimal("0.90"));
        source.setFirstHand(Boolean.TRUE);
        source.setStatus(SourceStatus.FETCHED);
        return source;
    }
}
