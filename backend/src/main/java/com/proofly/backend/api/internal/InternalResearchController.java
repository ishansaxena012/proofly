package com.proofly.backend.api.internal;

import com.proofly.backend.api.internal.dto.ClaimUpsertRequest;
import com.proofly.backend.api.internal.dto.EventRequest;
import com.proofly.backend.api.internal.dto.EvidenceBulkRequest;
import com.proofly.backend.api.internal.dto.IngestAck;
import com.proofly.backend.api.internal.dto.ProductUpdateRequest;
import com.proofly.backend.api.internal.dto.ReportUpsertRequest;
import com.proofly.backend.api.internal.dto.SourceUpsertRequest;
import com.proofly.backend.api.internal.dto.StatusUpdateRequest;
import com.proofly.backend.service.ResearchIngestService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The callback API the Python AI service pushes results into (docs/API.md §Internal API).
 *
 * <p>Every route under {@code /internal/**} is gated on the {@code X-Internal-Key} header
 * by {@code InternalApiKeyFilter}; there is no end-user identity on these requests, and
 * they are never reachable from the browser-facing chain.
 */
@RestController
@RequestMapping("/internal/v1/research/{id}")
@Tag(name = "Internal", description = "AI service → backend callbacks (X-Internal-Key required)")
@SecurityRequirement(name = "internalApiKey")
public class InternalResearchController {

    private final ResearchIngestService ingestService;

    public InternalResearchController(ResearchIngestService ingestService) {
        this.ingestService = ingestService;
    }

    @PostMapping("/status")
    @Operation(summary = "Advance the job state machine")
    public IngestAck updateStatus(@PathVariable("id") UUID id,
                                  @Valid @RequestBody StatusUpdateRequest request) {
        return ingestService.updateStatus(id, request);
    }

    @PostMapping("/product")
    @Operation(summary = "Store the resolved product identity")
    public IngestAck updateProduct(@PathVariable("id") UUID id,
                                   @Valid @RequestBody ProductUpdateRequest request) {
        return ingestService.updateProduct(id, request);
    }

    @PostMapping("/events")
    @Operation(summary = "Append a progress event and fan it out to SSE subscribers")
    public IngestAck recordEvent(@PathVariable("id") UUID id,
                                 @Valid @RequestBody EventRequest request) {
        return ingestService.recordEvent(id, request);
    }

    @PostMapping("/sources")
    @Operation(summary = "Bulk upsert research sources")
    public IngestAck upsertSources(@PathVariable("id") UUID id,
                                   @Valid @RequestBody SourceUpsertRequest request) {
        return ingestService.upsertSources(id, request);
    }

    @PostMapping("/evidence")
    @Operation(summary = "Bulk insert extracted evidence")
    public IngestAck insertEvidence(@PathVariable("id") UUID id,
                                    @Valid @RequestBody EvidenceBulkRequest request) {
        return ingestService.insertEvidence(id, request);
    }

    @PostMapping("/claims")
    @Operation(summary = "Bulk upsert claims and their evidence edges")
    public IngestAck upsertClaims(@PathVariable("id") UUID id,
                                  @Valid @RequestBody ClaimUpsertRequest request) {
        return ingestService.upsertClaims(id, request);
    }

    @PostMapping("/report")
    @Operation(summary = "Store the final report and finalise the job")
    public IngestAck saveReport(@PathVariable("id") UUID id,
                                @Valid @RequestBody ReportUpsertRequest request) {
        return ingestService.saveReport(id, request);
    }
}
