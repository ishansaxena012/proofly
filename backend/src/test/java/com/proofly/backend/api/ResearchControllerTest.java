package com.proofly.backend.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.proofly.backend.api.dto.CreateResearchResponse;
import com.proofly.backend.api.dto.EvidenceDto;
import com.proofly.backend.api.dto.FollowupResponse;
import com.proofly.backend.api.dto.ProductDto;
import com.proofly.backend.api.dto.ReportDto;
import com.proofly.backend.api.dto.ResearchJobDto;
import com.proofly.backend.api.dto.SourceDto;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ReportNotReadyException;
import com.proofly.backend.domain.EvidenceType;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.domain.SourceChannel;
import com.proofly.backend.domain.SourceStatus;
import com.proofly.backend.domain.SourceType;
import com.proofly.backend.service.FollowupService;
import com.proofly.backend.service.ReportService;
import com.proofly.backend.service.ResearchJobService;
import com.proofly.backend.sse.ResearchEventStreamService;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@WebMvcTest(controllers = ResearchController.class)
@AutoConfigureMockMvc(addFilters = false)
class ResearchControllerTest {

    private static final UUID JOB = UUID.fromString("aaaa1111-2222-3333-4444-555555555555");

    @Autowired private MockMvc mockMvc;

    @MockitoBean private ResearchJobService researchJobService;
    @MockitoBean private ReportService reportService;
    @MockitoBean private FollowupService followupService;
    @MockitoBean private ResearchEventStreamService eventStreamService;

    // ── POST /api/v1/research ────────────────────────────────────────────────

    @Test
    void acceptsAResearchRequestWith202() throws Exception {
        when(researchJobService.createResearchJob(any()))
                .thenReturn(new CreateResearchResponse(JOB, ResearchJobStatus.QUEUED));

        mockMvc.perform(post("/api/v1/research")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"productQuery\": \"Sony WH-1000XM6\"}"))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.researchJobId").value(JOB.toString()))
                .andExpect(jsonPath("$.status").value("QUEUED"));
    }

    @Test
    void rejectsAnEmptyProductQueryWithTheContractErrorShape() throws Exception {
        mockMvc.perform(post("/api/v1/research")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"productQuery\": \"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("productQuery")))
                .andExpect(jsonPath("$.timestamp").exists());
    }

    @Test
    void rejectsAMissingProductQuery() throws Exception {
        mockMvc.perform(post("/api/v1/research")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"));
    }

    @Test
    void rejectsMalformedJson() throws Exception {
        mockMvc.perform(post("/api/v1/research")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{not json"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"));
    }

    // ── GET /api/v1/research/{id} ────────────────────────────────────────────

    @Test
    void servesTheJobStatusPayload() throws Exception {
        when(researchJobService.getResearchJob(JOB)).thenReturn(new ResearchJobDto(
                JOB, ResearchJobStatus.RESEARCHING, "RESEARCHING", true,
                new ProductDto(UUID.randomUUID(), "Sony WH-1000XM6", "Sony WH-1000XM6", "Sony",
                        "Headphones", "WH-1000XM6"),
                12, 34, 9, 7, null, null,
                OffsetDateTime.now(), OffsetDateTime.now(), null));

        mockMvc.perform(get("/api/v1/research/{id}", JOB))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("RESEARCHING"))
                .andExpect(jsonPath("$.demoMode").value(true))
                .andExpect(jsonPath("$.product.brand").value("Sony"))
                .andExpect(jsonPath("$.sourceCount").value(12))
                .andExpect(jsonPath("$.verifiedClaimCount").value(7))
                .andExpect(jsonPath("$.completedAt").doesNotExist());
    }

    @Test
    void reportsAnUnknownOrForeignJobAs404() throws Exception {
        when(researchJobService.getResearchJob(JOB))
                .thenThrow(ApiException.notFound("Research job " + JOB + " was not found"));

        mockMvc.perform(get("/api/v1/research/{id}", JOB))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.errorCode").value("NOT_FOUND"));
    }

    @Test
    void rejectsANonUuidJobId() throws Exception {
        mockMvc.perform(get("/api/v1/research/{id}", "not-a-uuid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"));
    }

    // ── report ───────────────────────────────────────────────────────────────

    @Test
    void servesTheReportOnceTheJobIsComplete() throws Exception {
        when(reportService.getReport(JOB)).thenReturn(new ReportDto(
                JOB, true, new BigDecimal("82"), "Recommended with caveats", new BigDecimal("0.74"),
                "Summary", List.of(), List.of(), List.of(), List.of(), List.of(), List.of(), List.of(),
                null, List.of("Commuters"), List.of(), List.of(), List.of(), List.of(),
                OffsetDateTime.now(), 1));

        mockMvc.perform(get("/api/v1/research/{id}/report", JOB))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.researchJobId").value(JOB.toString()))
                .andExpect(jsonPath("$.overallScore").value(82))
                .andExpect(jsonPath("$.demoMode").value(true))
                .andExpect(jsonPath("$.whoShouldBuy[0]").value("Commuters"));
    }

    @Test
    void refusesTheReportWith409AndTheCurrentStatus() throws Exception {
        when(reportService.getReport(JOB)).thenThrow(new ReportNotReadyException(ResearchJobStatus.RESEARCHING));

        mockMvc.perform(get("/api/v1/research/{id}/report", JOB))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.status").value("RESEARCHING"))
                .andExpect(jsonPath("$.errorCode").value("INSUFFICIENT_DATA"));
    }

    // ── sources / evidence ───────────────────────────────────────────────────

    @Test
    void listsSources() throws Exception {
        when(researchJobService.getSources(JOB)).thenReturn(List.of(new SourceDto(
                UUID.randomUUID(), SourceChannel.REDDIT, "https://example.test/thread", "A thread",
                SourceType.FORUM_POST, new BigDecimal("0.4"), true, null, SourceStatus.FETCHED)));

        mockMvc.perform(get("/api/v1/research/{id}/sources", JOB))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].channel").value("REDDIT"))
                .andExpect(jsonPath("$[0].sourceType").value("FORUM_POST"))
                .andExpect(jsonPath("$[0].firstHand").value(true));
    }

    @Test
    void listsEvidenceAndPassesTheTopicFilterThrough() throws Exception {
        when(researchJobService.getEvidence(eq(JOB), eq("Battery"))).thenReturn(List.of(new EvidenceDto(
                UUID.randomUUID(), UUID.randomUUID(), "Battery", null, EvidenceType.MEASUREMENT, null,
                "38 hours measured")));

        mockMvc.perform(get("/api/v1/research/{id}/evidence", JOB).param("topic", "Battery"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].topic").value("Battery"))
                .andExpect(jsonPath("$[0].evidenceType").value("MEASUREMENT"));

        verify(researchJobService).getEvidence(JOB, "Battery");
    }

    @Test
    void listsAllEvidenceWhenNoTopicIsGiven() throws Exception {
        when(researchJobService.getEvidence(JOB, null)).thenReturn(List.of());

        mockMvc.perform(get("/api/v1/research/{id}/evidence", JOB)).andExpect(status().isOk());

        verify(researchJobService).getEvidence(JOB, null);
    }

    // ── followup ─────────────────────────────────────────────────────────────

    @Test
    void answersAFollowupQuestion() throws Exception {
        UUID evidenceId = UUID.randomUUID();
        when(followupService.ask(eq(JOB), any()))
                .thenReturn(new FollowupResponse("About 38 hours.", List.of(evidenceId)));

        mockMvc.perform(post("/api/v1/research/{id}/followup", JOB)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"question\": \"How is battery life?\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.answer").value("About 38 hours."))
                .andExpect(jsonPath("$.citedEvidenceIds[0]").value(evidenceId.toString()));
    }

    @Test
    void rejectsABlankFollowupQuestion() throws Exception {
        mockMvc.perform(post("/api/v1/research/{id}/followup", JOB)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"question\": \"  \"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("VALIDATION_ERROR"));
    }

    // ── SSE ──────────────────────────────────────────────────────────────────

    @Test
    void streamsEventsAsServerSentEvents() throws Exception {
        SseEmitter emitter = new SseEmitter(10_000L);
        when(eventStreamService.subscribe(JOB)).thenReturn(emitter);

        MvcResult result = mockMvc.perform(get("/api/v1/research/{id}/events", JOB)
                        .accept(MediaType.TEXT_EVENT_STREAM))
                .andExpect(request().asyncStarted())
                .andReturn();

        emitter.send(SseEmitter.event()
                .id("1")
                .name("REPORT_COMPLETED")
                .data(Map.of("message", "Report ready"), MediaType.APPLICATION_JSON));
        emitter.complete();

        mockMvc.perform(MockMvcRequestBuilders.asyncDispatch(result))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_EVENT_STREAM));

        String body = result.getResponse().getContentAsString();
        assertThat(body).contains("event:REPORT_COMPLETED");
        assertThat(body).contains("Report ready");
    }
}
