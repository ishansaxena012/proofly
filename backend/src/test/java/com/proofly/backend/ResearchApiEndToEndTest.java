package com.proofly.backend;

import static org.assertj.core.api.Assertions.assertThat;

import com.proofly.backend.api.dto.CreateResearchResponse;
import com.proofly.backend.api.dto.ReportDto;
import com.proofly.backend.api.dto.ResearchJobDto;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.queue.ResearchJobDispatcher;
import com.proofly.backend.repository.UserAccountRepository;
import com.proofly.backend.security.InternalApiKeyFilter;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.function.Predicate;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

/**
 * Boots the whole application — real Postgres, real Redis, real filter chains — and drives
 * it exactly the way the frontend and the AI service will.
 *
 * <p>No live network is involved: the AI service is represented by an address that refuses
 * connections, which is itself one of the behaviours under test (a dead AI service must
 * fail the job cleanly rather than hang or crash the dispatcher). Everything the AI service
 * would push back is posted through the internal API by the test.
 *
 * <p>The scheduled dispatcher poll is pushed an hour out so the test can trigger dispatch
 * deliberately; otherwise it would race with the jobs the ingest test wants to drive by
 * hand.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers(disabledWithoutDocker = true)
class ResearchApiEndToEndTest {

    private static final String INTERNAL_KEY = "e2e-internal-key";

    @Container
    @SuppressWarnings("resource")
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"))
            .withDatabaseName("proofly")
            .withUsername("postgres")
            .withPassword("postgres");

    @Container
    @SuppressWarnings("resource")
    static final GenericContainer<?> REDIS = new GenericContainer<>(DockerImageName.parse("redis:7-alpine"))
            .withExposedPorts(6379)
            .waitingFor(Wait.forListeningPort());

    @DynamicPropertySource
    static void configuration(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("spring.data.redis.url",
                () -> "redis://" + REDIS.getHost() + ":" + REDIS.getMappedPort(6379) + "/0");
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "none");
        registry.add("proofly.security.internal-api-key", () -> INTERNAL_KEY);
        registry.add("proofly.security.jwt-issuer-uri", () -> "");
        // Port 1 is reserved and refuses connections immediately: a deterministic
        // stand-in for "the AI service is down", with no live network involved.
        registry.add("proofly.ai.base-url", () -> "http://127.0.0.1:1");
        registry.add("proofly.ai.max-dispatch-attempts", () -> "1");
        registry.add("proofly.ai.dispatch-retry-backoff", () -> "1ms");
        registry.add("proofly.research.sse-timeout", () -> "5s");
        registry.add("proofly-dispatcher.poll-interval-ms", () -> "3600000");
    }

    @org.springframework.boot.test.web.server.LocalServerPort private int port;

    @Autowired private TestRestTemplate rest;
    @Autowired private ResearchJobDispatcher dispatcher;
    @Autowired private UserAccountRepository users;

    private static HttpHeaders userAuth(UUID userId) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth("dev-" + userId);
        headers.setContentType(MediaType.APPLICATION_JSON);
        return headers;
    }

    private static HttpHeaders internalAuth() {
        HttpHeaders headers = new HttpHeaders();
        headers.set(InternalApiKeyFilter.HEADER, INTERNAL_KEY);
        headers.setContentType(MediaType.APPLICATION_JSON);
        return headers;
    }

    private UUID startJob(UUID userId, String query) {
        ResponseEntity<CreateResearchResponse> created = rest.exchange(
                "/api/v1/research", HttpMethod.POST,
                new HttpEntity<>(Map.of("productQuery", query), userAuth(userId)),
                CreateResearchResponse.class);

        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        assertThat(created.getBody()).isNotNull();
        assertThat(created.getBody().status()).isEqualTo(ResearchJobStatus.QUEUED);
        return created.getBody().researchJobId();
    }

    private ResearchJobDto readJob(UUID userId, UUID jobId) {
        ResponseEntity<ResearchJobDto> response = rest.exchange(
                "/api/v1/research/" + jobId, HttpMethod.GET,
                new HttpEntity<>(userAuth(userId)), ResearchJobDto.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        return response.getBody();
    }

    private ResearchJobDto awaitJob(UUID userId, UUID jobId, Predicate<ResearchJobDto> condition) {
        Instant deadline = Instant.now().plus(Duration.ofSeconds(30));
        ResearchJobDto last = null;
        while (Instant.now().isBefore(deadline)) {
            last = readJob(userId, jobId);
            if (condition.test(last)) {
                return last;
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        throw new AssertionError("Job never reached the expected state; last seen: " + last);
    }

    private void post(String path, Object body) {
        ResponseEntity<String> response = rest.exchange(path, HttpMethod.POST,
                new HttpEntity<>(body, internalAuth()), String.class);
        assertThat(response.getStatusCode())
                .as("POST %s -> %s", path, response.getBody())
                .isEqualTo(HttpStatus.OK);
    }

    // ── the queue → dispatcher → dead AI service path ────────────────────────

    @Test
    void aJobWhoseAiServiceIsUnreachableFailsCleanlyWithAgentFailure() {
        UUID userId = UUID.randomUUID();
        UUID jobId = startJob(userId, "Sony WH-1000XM6");

        assertThat(users.findById(userId))
                .as("the dev user row is provisioned on first sight")
                .isPresent();
        assertThat(readJob(userId, jobId).status()).isEqualTo(ResearchJobStatus.QUEUED);

        dispatcher.pollQueue();

        ResearchJobDto failed = awaitJob(userId, jobId, job -> job.status().isTerminal());
        assertThat(failed.status()).isEqualTo(ResearchJobStatus.FAILED);
        assertThat(failed.errorCode()).isEqualTo("AGENT_FAILURE");
        assertThat(failed.completedAt()).isNotNull();
        assertThat(failed.product().rawQuery()).isEqualTo("Sony WH-1000XM6");
    }

    // ── ownership ────────────────────────────────────────────────────────────

    @Test
    void anotherUsersJobIsIndistinguishableFromAMissingOne() {
        UUID owner = UUID.randomUUID();
        UUID intruder = UUID.randomUUID();
        UUID jobId = startJob(owner, "Sony WH-1000XM6");

        for (String path : new String[]{"", "/report", "/sources", "/evidence"}) {
            ResponseEntity<String> response = rest.exchange(
                    "/api/v1/research/" + jobId + path, HttpMethod.GET,
                    new HttpEntity<>(userAuth(intruder)), String.class);
            assertThat(response.getStatusCode())
                    .as("GET /api/v1/research/{id}%s as a non-owner", path)
                    .isEqualTo(HttpStatus.NOT_FOUND);
            assertThat(response.getBody()).contains("NOT_FOUND");
        }
    }

    @Test
    void anUnauthenticatedCallerGets401() {
        ResponseEntity<String> response = rest.getForEntity(
                "/api/v1/research/" + UUID.randomUUID(), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void theInternalApiRejectsCallersWithoutTheSharedKey() {
        ResponseEntity<String> response = rest.exchange(
                "/internal/v1/research/" + UUID.randomUUID() + "/status", HttpMethod.POST,
                new HttpEntity<>(Map.of("status", "RUNNING"), new HttpHeaders()), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    // ── the full AI-service callback pipeline ────────────────────────────────

    @Test
    void theInternalCallbacksDriveAJobAllTheWayToAReadableReport() throws Exception {
        UUID userId = UUID.randomUUID();
        UUID jobId = startJob(userId, "Sony WH-1000XM6");
        String base = "/internal/v1/research/" + jobId;

        post(base + "/status", Map.of("status", "RUNNING", "currentStage", "RUNNING"));
        post(base + "/product", Map.of(
                "canonicalName", "Sony WH-1000XM6", "brand", "Sony",
                "category", "Headphones", "model", "WH-1000XM6", "resolutionConfidence", 0.95));
        post(base + "/events", Map.of(
                "eventType", "WEB_RESEARCH_COMPLETED", "message", "Fetched 2 pages",
                "payload", Map.of("pages", 2)));

        UUID sourceId = UUID.randomUUID();
        post(base + "/sources", Map.of("sources", java.util.List.of(
                Map.of("id", sourceId.toString(), "channel", "WEB",
                        "url", "https://example.test/review", "title", "A professional review",
                        "sourceType", "PROFESSIONAL_REVIEW", "authorityScore", 0.9,
                        "firstHand", true, "status", "FETCHED"),
                Map.of("channel", "YOUTUBE", "url", "https://example.test/video",
                        "status", "FAILED", "failureReason", "Transcript unavailable"))));

        UUID supporting = UUID.randomUUID();
        UUID contradicting = UUID.randomUUID();
        post(base + "/evidence", Map.of("evidence", java.util.List.of(
                Map.of("id", supporting.toString(), "sourceId", sourceId.toString(),
                        "topic", "Microphone", "sentiment", "POSITIVE", "evidenceType", "EXPERT_OPINION",
                        "strength", "STRONG", "text", "Call quality is clear indoors"),
                Map.of("id", contradicting.toString(), "sourceUrl", "https://example.test/review",
                        "topic", "Microphone", "sentiment", "NEGATIVE", "evidenceType", "CUSTOMER_EXPERIENCE",
                        "strength", "MODERATE", "text", "Unusable in strong wind"))));

        UUID claimId = UUID.randomUUID();
        post(base + "/claims", Map.of(
                "claims", java.util.List.of(Map.of(
                        "id", claimId.toString(), "topic", "Microphone",
                        "statement", "Microphone quality depends on the environment",
                        "status", "CONTESTED", "confidence", 0.6)),
                "claimEvidence", java.util.List.of(
                        Map.of("claimId", claimId.toString(), "evidenceId", supporting.toString(),
                                "relationship", "SUPPORTS"),
                        Map.of("claimId", claimId.toString(), "evidenceId", contradicting.toString(),
                                "relationship", "CONTRADICTS"))));

        // Before the report exists, the report endpoint refuses with 409 + the status.
        ResponseEntity<String> tooEarly = rest.exchange(
                "/api/v1/research/" + jobId + "/report", HttpMethod.GET,
                new HttpEntity<>(userAuth(userId)), String.class);
        assertThat(tooEarly.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(tooEarly.getBody()).contains("\"status\":\"RUNNING\"");

        // The ai-service posts the whole public report DTO plus a sections array; the
        // read-side fields it echoes back (researchJobId, demoMode, sources, claims) must
        // be ignored rather than trusted.
        java.util.Map<String, Object> reportBody = new java.util.LinkedHashMap<>();
        reportBody.put("researchJobId", UUID.randomUUID().toString());
        reportBody.put("demoMode", false);
        reportBody.put("sources", java.util.List.of(Map.of("id", UUID.randomUUID().toString())));
        reportBody.put("claims", java.util.List.of(Map.of("id", UUID.randomUUID().toString())));
        reportBody.putAll(Map.of(
                "overallScore", 82, "verdict", "Recommended with caveats", "confidence", 0.74,
                "executiveSummary", "A strong all-rounder with a situational microphone.",
                "finalStatus", "COMPLETED", "verifiedClaimCount", 0,
                "sections", java.util.List.of(
                        Map.of("sectionType", "CATEGORY_ANALYSIS", "title", "Categories", "orderIndex", 0,
                                "content", java.util.List.of(
                                        Map.of("category", "Sound Quality", "score", 88, "confidence", 0.8))),
                        Map.of("sectionType", "CONFLICTS", "title", "Conflicts", "orderIndex", 1,
                                "content", java.util.List.of(Map.of(
                                        "topic", "Microphone quality",
                                        "positionA", Map.of("text", "Good indoors",
                                                "evidenceIds", java.util.List.of(supporting.toString())),
                                        "positionB", Map.of("text", "Poor outdoors",
                                                "evidenceIds", java.util.List.of(contradicting.toString())),
                                        "explanation", "Context-dependent: wind noise.",
                                        "resolved", false))),
                        Map.of("sectionType", "CAVEATS", "title", "Caveats", "orderIndex", 2,
                                "content", java.util.List.of("YouTube research was unavailable for this run")))));
        post(base + "/report", reportBody);

        // ── the job is now readable exactly as the frontend expects ──────────
        ResearchJobDto job = readJob(userId, jobId);
        assertThat(job.status()).isEqualTo(ResearchJobStatus.COMPLETED);
        assertThat(job.product().canonicalName()).isEqualTo("Sony WH-1000XM6");
        assertThat(job.sourceCount()).isEqualTo(2);
        assertThat(job.evidenceCount()).isEqualTo(2);
        assertThat(job.claimCount()).isEqualTo(1);
        assertThat(job.completedAt()).isNotNull();

        ResponseEntity<ReportDto> report = rest.exchange(
                "/api/v1/research/" + jobId + "/report", HttpMethod.GET,
                new HttpEntity<>(userAuth(userId)), ReportDto.class);
        assertThat(report.getStatusCode()).isEqualTo(HttpStatus.OK);
        ReportDto body = report.getBody();
        assertThat(body).isNotNull();
        assertThat(body.overallScore()).isEqualByComparingTo("82");
        assertThat(body.demoMode()).isTrue();
        assertThat(body.categoryScores()).singleElement()
                .satisfies(score -> assertThat(score.category()).isEqualTo("Sound Quality"));
        assertThat(body.caveats()).containsExactly("YouTube research was unavailable for this run");
        assertThat(body.sources()).hasSize(2);
        assertThat(body.conflicts()).singleElement().satisfies(conflict -> {
            assertThat(conflict.positionA().evidenceIds()).containsExactly(supporting);
            assertThat(conflict.positionB().evidenceIds()).containsExactly(contradicting);
        });
        assertThat(body.claims()).singleElement().satisfies(claim -> {
            assertThat(claim.id()).isEqualTo(claimId);
            assertThat(claim.supportingEvidence()).singleElement()
                    .satisfies(item -> assertThat(item.text()).isEqualTo("Call quality is clear indoors"));
            assertThat(claim.contradictingEvidence()).singleElement()
                    .satisfies(item -> assertThat(item.text()).isEqualTo("Unusable in strong wind"));
        });

        // ── sources / evidence listings ──────────────────────────────────────
        ResponseEntity<String> sources = rest.exchange(
                "/api/v1/research/" + jobId + "/sources", HttpMethod.GET,
                new HttpEntity<>(userAuth(userId)), String.class);
        // Failed sources stay in the listing — a channel that fell over is part of the
        // audit trail, not something to hide. (The listing shape is fixed by docs/API.md,
        // so the reason itself surfaces through the report's CAVEATS section.)
        assertThat(sources.getBody())
                .contains("PROFESSIONAL_REVIEW")
                .contains("\"channel\":\"YOUTUBE\",\"url\":\"https://example.test/video\"")
                .contains("\"status\":\"FAILED\"");

        ResponseEntity<String> filtered = rest.exchange(
                "/api/v1/research/" + jobId + "/evidence?topic=microphone", HttpMethod.GET,
                new HttpEntity<>(userAuth(userId)), String.class);
        assertThat(filtered.getBody()).contains("Call quality is clear indoors");

        ResponseEntity<String> noMatches = rest.exchange(
                "/api/v1/research/" + jobId + "/evidence?topic=battery", HttpMethod.GET,
                new HttpEntity<>(userAuth(userId)), String.class);
        assertThat(noMatches.getBody()).isEqualTo("[]");

        // ── SSE replays the whole log, including the query-parameter auth path ─
        // Read with the JDK client rather than RestTemplate, which has no converter for
        // text/event-stream.
        String stream = readEventStream(
                "/api/v1/research/" + jobId + "/events?access_token=dev-" + userId);

        assertThat(stream)
                .contains("event:PRODUCT_IDENTIFIED")
                .contains("event:WEB_RESEARCH_COMPLETED")
                .contains("event:CLAIMS_GENERATED")
                .contains("event:REPORT_COMPLETED")
                .contains("Fetched 2 pages");
    }

    /**
     * Reads a whole SSE response. Safe to block on because the job is already terminal:
     * the server replays the log and closes the stream rather than holding it open.
     */
    private String readEventStream(String path) throws Exception {
        java.net.http.HttpRequest request = java.net.http.HttpRequest.newBuilder()
                .uri(java.net.URI.create("http://localhost:" + port + path))
                .header("Accept", MediaType.TEXT_EVENT_STREAM_VALUE)
                .timeout(Duration.ofSeconds(20))
                .GET()
                .build();
        try (java.net.http.HttpClient client = java.net.http.HttpClient.newHttpClient()) {
            java.net.http.HttpResponse<String> response =
                    client.send(request, java.net.http.HttpResponse.BodyHandlers.ofString());
            assertThat(response.statusCode()).isEqualTo(200);
            assertThat(response.headers().firstValue("Content-Type").orElse(""))
                    .startsWith(MediaType.TEXT_EVENT_STREAM_VALUE);
            return response.body();
        }
    }

    @Test
    void openApiAndHealthAreServedWithoutAuthentication() {
        assertThat(rest.getForEntity("/actuator/health", String.class).getStatusCode())
                .isEqualTo(HttpStatus.OK);

        ResponseEntity<String> apiDocs = rest.getForEntity("/v3/api-docs", String.class);
        assertThat(apiDocs.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(apiDocs.getBody())
                .contains("/api/v1/research")
                .contains("/internal/v1/research/{id}/report");
    }
}
