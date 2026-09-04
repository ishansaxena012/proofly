package com.proofly.backend.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.proofly.backend.TestFixtures;
import com.proofly.backend.api.dto.CreateResearchResponse;
import com.proofly.backend.api.dto.ResearchJobDto;
import com.proofly.backend.api.internal.InternalResearchController;
import com.proofly.backend.api.internal.dto.IngestAck;
import com.proofly.backend.config.ProoflyProperties;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.security.InternalApiKeyFilter;
import com.proofly.backend.security.SecurityConfig;
import com.proofly.backend.service.FollowupService;
import com.proofly.backend.service.ReportService;
import com.proofly.backend.service.ResearchIngestService;
import com.proofly.backend.service.ResearchJobService;
import com.proofly.backend.sse.ResearchEventStreamService;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * End-to-end filter-chain behaviour: the browser-facing API needs a user identity, the
 * internal API needs the shared key, and neither one accepts the other's credential.
 */
@WebMvcTest(controllers = {ResearchController.class, InternalResearchController.class})
@Import(SecurityConfig.class)
@EnableConfigurationProperties(ProoflyProperties.class)
@TestPropertySource(properties = {
        "proofly.security.internal-api-key=" + TestFixtures.INTERNAL_KEY,
        "proofly.security.jwt-issuer-uri="
})
class ApiSecurityTest {

    private static final UUID JOB = UUID.fromString("bbbb1111-2222-3333-4444-555555555555");
    private static final UUID USER = UUID.fromString("cccc1111-2222-3333-4444-555555555555");

    @Autowired private MockMvc mockMvc;

    @MockitoBean private ResearchJobService researchJobService;
    @MockitoBean private ReportService reportService;
    @MockitoBean private FollowupService followupService;
    @MockitoBean private ResearchEventStreamService eventStreamService;
    @MockitoBean private ResearchIngestService ingestService;

    // ── public API ───────────────────────────────────────────────────────────

    @Test
    void anUnauthenticatedCallIsRejectedWith401() throws Exception {
        mockMvc.perform(get("/api/v1/research/{id}", JOB))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.errorCode").value("UNAUTHORIZED"));

        verify(researchJobService, never()).getResearchJob(any());
    }

    @Test
    void aDevBearerTokenAuthenticatesWhenNoJwtIssuerIsConfigured() throws Exception {
        when(researchJobService.getResearchJob(JOB)).thenReturn(new ResearchJobDto(
                JOB, ResearchJobStatus.QUEUED, "QUEUED", true, null, 0, 0, 0, 0, null, null,
                OffsetDateTime.now(), null, null));

        mockMvc.perform(get("/api/v1/research/{id}", JOB)
                        .header("Authorization", "Bearer dev-" + USER))
                .andExpect(status().isOk());
    }

    @Test
    void aMalformedDevTokenIsStillUnauthenticated() throws Exception {
        mockMvc.perform(get("/api/v1/research/{id}", JOB)
                        .header("Authorization", "Bearer dev-nonsense"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void theSseStreamAcceptsTheTokenAsAQueryParameterBecauseEventSourceCannotSendHeaders()
            throws Exception {
        when(eventStreamService.subscribe(JOB)).thenReturn(new SseEmitter(1_000L));

        mockMvc.perform(get("/api/v1/research/{id}/events", JOB)
                        .param("access_token", "dev-" + USER)
                        .accept(MediaType.TEXT_EVENT_STREAM))
                .andExpect(request().asyncStarted());

        verify(eventStreamService).subscribe(JOB);
    }

    @Test
    void theSseStreamStillRejectsAMissingToken() throws Exception {
        mockMvc.perform(get("/api/v1/research/{id}/events", JOB)
                        .accept(MediaType.TEXT_EVENT_STREAM))
                .andExpect(status().isUnauthorized());

        verify(eventStreamService, never()).subscribe(any());
    }

    @Test
    void aQueryParameterTokenDoesNotWorkOnOtherRoutes() throws Exception {
        mockMvc.perform(get("/api/v1/research/{id}", JOB)
                        .param("access_token", "dev-" + USER))
                .andExpect(status().isUnauthorized());

        verify(researchJobService, never()).getResearchJob(any());
    }

    @Test
    void theInternalKeyDoesNotUnlockThePublicApi() throws Exception {
        mockMvc.perform(post("/api/v1/research")
                        .header(InternalApiKeyFilter.HEADER, TestFixtures.INTERNAL_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"productQuery\": \"Sony WH-1000XM6\"}"))
                .andExpect(status().isUnauthorized());

        verify(researchJobService, never()).createResearchJob(any());
    }

    @Test
    void anAuthenticatedUserCanStartAJob() throws Exception {
        when(researchJobService.createResearchJob(any()))
                .thenReturn(new CreateResearchResponse(JOB, ResearchJobStatus.QUEUED));

        mockMvc.perform(post("/api/v1/research")
                        .header("Authorization", "Bearer dev-" + USER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"productQuery\": \"Sony WH-1000XM6\"}"))
                .andExpect(status().isAccepted());
    }

    // ── internal API ─────────────────────────────────────────────────────────

    @Test
    void theInternalApiRejectsAMissingKeyWith403() throws Exception {
        mockMvc.perform(post("/internal/v1/research/{id}/status", JOB)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"status\": \"RUNNING\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.errorCode").value("FORBIDDEN"));

        verify(ingestService, never()).updateStatus(any(), any());
    }

    @Test
    void theInternalApiRejectsAWrongKey() throws Exception {
        mockMvc.perform(post("/internal/v1/research/{id}/status", JOB)
                        .header(InternalApiKeyFilter.HEADER, "wrong-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"status\": \"RUNNING\"}"))
                .andExpect(status().isForbidden());
    }

    @Test
    void aUserBearerTokenDoesNotUnlockTheInternalApi() throws Exception {
        mockMvc.perform(post("/internal/v1/research/{id}/status", JOB)
                        .header("Authorization", "Bearer dev-" + USER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"status\": \"RUNNING\"}"))
                .andExpect(status().isForbidden());
    }

    @Test
    void theInternalApiAcceptsTheSharedKey() throws Exception {
        when(ingestService.updateStatus(eq(JOB), any()))
                .thenReturn(IngestAck.ok(JOB, ResearchJobStatus.RUNNING));

        mockMvc.perform(post("/internal/v1/research/{id}/status", JOB)
                        .header(InternalApiKeyFilter.HEADER, TestFixtures.INTERNAL_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"status\": \"RUNNING\", \"currentStage\": \"RUNNING\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("RUNNING"));
    }

    @Test
    void theInternalApiStillValidatesItsBodies() throws Exception {
        mockMvc.perform(post("/internal/v1/research/{id}/status", JOB)
                        .header(InternalApiKeyFilter.HEADER, TestFixtures.INTERNAL_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"));
    }

    @Test
    void internalSourceUpsertsRequireAChannelAndUrl() throws Exception {
        mockMvc.perform(post("/internal/v1/research/{id}/sources", JOB)
                        .header(InternalApiKeyFilter.HEADER, TestFixtures.INTERNAL_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"sources\": [{\"title\": \"No url\"}]}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"));

        verify(ingestService, never()).upsertSources(any(), any());
    }

    @Test
    void internalEvidenceInsertsAcceptAWellFormedBatch() throws Exception {
        UUID sourceId = UUID.randomUUID();
        UUID evidenceId = UUID.randomUUID();
        when(ingestService.insertEvidence(eq(JOB), any()))
                .thenReturn(IngestAck.of(JOB, ResearchJobStatus.EXTRACTING_EVIDENCE, List.of(evidenceId)));

        mockMvc.perform(post("/internal/v1/research/{id}/evidence", JOB)
                        .header(InternalApiKeyFilter.HEADER, TestFixtures.INTERNAL_KEY)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"evidence": [{"sourceId": "%s", "topic": "Battery",
                                  "evidenceType": "MEASUREMENT", "text": "38 hours measured"}]}
                                """.formatted(sourceId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.processed").value(1))
                .andExpect(jsonPath("$.ids[0]").value(evidenceId.toString()));
    }
}
