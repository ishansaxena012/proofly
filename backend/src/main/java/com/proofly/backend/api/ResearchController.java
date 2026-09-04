package com.proofly.backend.api;

import com.proofly.backend.api.dto.CreateResearchRequest;
import com.proofly.backend.api.dto.CreateResearchResponse;
import com.proofly.backend.api.dto.EvidenceDto;
import com.proofly.backend.api.dto.FollowupRequest;
import com.proofly.backend.api.dto.FollowupResponse;
import com.proofly.backend.api.dto.ReportDto;
import com.proofly.backend.api.dto.ResearchJobDto;
import com.proofly.backend.api.dto.SourceDto;
import com.proofly.backend.api.error.ApiErrorResponse;
import com.proofly.backend.service.FollowupService;
import com.proofly.backend.service.ReportService;
import com.proofly.backend.service.ResearchJobService;
import com.proofly.backend.sse.ResearchEventStreamService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * The public research API (docs/API.md §Public REST API).
 *
 * <p>Thin by design: identity, ownership, state and assembly all live in the services. No
 * endpoint accepts a user id — the owner is always resolved from the validated token.
 */
@RestController
@RequestMapping("/api/v1/research")
@Tag(name = "Research", description = "Start research jobs and read their progress, evidence and report")
public class ResearchController {

    private final ResearchJobService researchJobService;
    private final ReportService reportService;
    private final FollowupService followupService;
    private final ResearchEventStreamService eventStreamService;

    public ResearchController(ResearchJobService researchJobService,
                              ReportService reportService,
                              FollowupService followupService,
                              ResearchEventStreamService eventStreamService) {
        this.researchJobService = researchJobService;
        this.reportService = reportService;
        this.followupService = followupService;
        this.eventStreamService = eventStreamService;
    }

    @PostMapping
    @Operation(summary = "Start a research job for one product")
    @ApiResponse(responseCode = "202", description = "Job accepted and queued")
    @ApiResponse(responseCode = "400", description = "Invalid or empty product query",
            content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    public ResponseEntity<CreateResearchResponse> createResearch(@Valid @RequestBody CreateResearchRequest request) {
        CreateResearchResponse response = researchJobService.createResearchJob(request);
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);
    }

    @GetMapping("/{id}")
    @Operation(summary = "Read a research job's status and progress counters")
    @ApiResponse(responseCode = "404", description = "No such job for this user",
            content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    public ResearchJobDto getResearch(@PathVariable("id") UUID id) {
        return researchJobService.getResearchJob(id);
    }

    @GetMapping("/{id}/report")
    @Operation(summary = "Read the finished report")
    @ApiResponse(responseCode = "409", description = "Job has not reached COMPLETED/PARTIALLY_COMPLETED",
            content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    public ReportDto getReport(@PathVariable("id") UUID id) {
        return reportService.getReport(id);
    }

    @GetMapping("/{id}/sources")
    @Operation(summary = "List every source the job attempted to use")
    public List<SourceDto> getSources(@PathVariable("id") UUID id) {
        return researchJobService.getSources(id);
    }

    @GetMapping("/{id}/evidence")
    @Operation(summary = "List extracted evidence, optionally filtered by topic")
    public List<EvidenceDto> getEvidence(@PathVariable("id") UUID id,
                                         @RequestParam(name = "topic", required = false) String topic) {
        return researchJobService.getEvidence(id, topic);
    }

    @GetMapping(path = "/{id}/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @Operation(summary = "Live progress stream (SSE)",
            description = "Replays the persisted event log first, then streams live events. "
                    + "The SSE event name is the event type; the data is "
                    + "{id, eventType, message, payload, createdAt}.")
    public SseEmitter streamEvents(@PathVariable("id") UUID id) {
        return eventStreamService.subscribe(id);
    }

    @PostMapping("/{id}/followup")
    @Operation(summary = "Ask an evidence-grounded follow-up question about a finished job")
    public FollowupResponse followup(@PathVariable("id") UUID id,
                                     @Valid @RequestBody FollowupRequest request) {
        return followupService.ask(id, request);
    }
}
