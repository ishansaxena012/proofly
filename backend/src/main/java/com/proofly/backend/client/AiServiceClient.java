package com.proofly.backend.client;

import com.proofly.backend.config.HttpClientConfig;
import com.proofly.backend.config.ProoflyProperties;
import com.proofly.backend.security.InternalApiKeyFilter;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

/**
 * The only place the backend talks to the Python AI service. Every failure is translated
 * into an {@link AiServiceException} carrying a contract error code, so callers never have
 * to reason about transport-level exceptions.
 */
@Component
public class AiServiceClient {

    private static final Logger log = LoggerFactory.getLogger(AiServiceClient.class);

    private final RestClient dispatchClient;
    private final RestClient followupClient;
    private final String internalApiKey;

    public AiServiceClient(@Qualifier(HttpClientConfig.DISPATCH_CLIENT) RestClient dispatchClient,
                           @Qualifier(HttpClientConfig.FOLLOWUP_CLIENT) RestClient followupClient,
                           ProoflyProperties properties) {
        this.dispatchClient = dispatchClient;
        this.followupClient = followupClient;
        this.internalApiKey = properties.security().internalApiKey();
    }

    /** Kicks off the LangGraph pipeline. Returns as soon as the AI service accepts the job. */
    public void execute(ExecuteResearchCommand command) {
        String operation = "research execute for job " + command.researchJobId();
        try {
            dispatchClient.post()
                    .uri("/internal/v1/research/execute")
                    .header(InternalApiKeyFilter.HEADER, internalApiKey)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(command)
                    .retrieve()
                    .toBodilessEntity();
            log.info("Dispatched research job {} to the AI service", command.researchJobId());
        } catch (RestClientResponseException ex) {
            throw AiServiceException.badResponse(operation, ex.getStatusCode().value(), ex);
        } catch (ResourceAccessException ex) {
            throw AiServiceException.unreachable(operation, ex);
        }
    }

    /** Evidence-grounded follow-up Q&amp;A. Synchronous: the caller is a user-facing request. */
    public AiFollowupResponse followup(UUID researchJobId, AiFollowupRequest request) {
        String operation = "followup for job " + researchJobId;
        try {
            AiFollowupResponse response = followupClient.post()
                    .uri("/internal/v1/research/{id}/followup", researchJobId)
                    .header(InternalApiKeyFilter.HEADER, internalApiKey)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(AiFollowupResponse.class);
            if (response == null) {
                throw new AiServiceException(com.proofly.backend.api.error.ErrorCode.AGENT_FAILURE,
                        "AI service returned an empty follow-up response", null);
            }
            return response;
        } catch (RestClientResponseException ex) {
            throw AiServiceException.badResponse(operation, ex.getStatusCode().value(), ex);
        } catch (ResourceAccessException ex) {
            throw AiServiceException.unreachable(operation, ex);
        }
    }

    /** Best-effort cancellation; never throws, because cancelling is advisory. */
    public boolean cancel(UUID researchJobId) {
        try {
            dispatchClient.post()
                    .uri("/internal/v1/research/{id}/cancel", researchJobId)
                    .header(InternalApiKeyFilter.HEADER, internalApiKey)
                    .retrieve()
                    .toBodilessEntity();
            return true;
        } catch (RuntimeException ex) {
            log.warn("Best-effort cancel of job {} failed: {}", researchJobId, ex.getMessage());
            return false;
        }
    }
}
