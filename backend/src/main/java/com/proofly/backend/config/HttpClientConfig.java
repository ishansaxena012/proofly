package com.proofly.backend.config;

import java.net.http.HttpClient;
import java.time.Duration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/**
 * HTTP clients for backend → ai-service calls.
 *
 * <p>Two clients exist because the two call shapes have very different latency profiles:
 * {@code /research/execute} returns {@code 202} immediately and must fail fast so the
 * dispatcher can retry, whereas an evidence-grounded follow-up question runs an LLM call
 * synchronously.
 */
@Configuration
public class HttpClientConfig {

    public static final String DISPATCH_CLIENT = "aiDispatchRestClient";
    public static final String FOLLOWUP_CLIENT = "aiFollowupRestClient";

    @Bean(DISPATCH_CLIENT)
    public RestClient aiDispatchRestClient(ProoflyProperties properties) {
        return build(properties.ai().baseUrl(), properties.ai().connectTimeout(), properties.ai().readTimeout());
    }

    @Bean(FOLLOWUP_CLIENT)
    public RestClient aiFollowupRestClient(ProoflyProperties properties) {
        return build(properties.ai().baseUrl(), properties.ai().connectTimeout(), properties.ai().followupTimeout());
    }

    private static RestClient build(String baseUrl, Duration connectTimeout, Duration readTimeout) {
        // Force HTTP/1.1: the JDK client's default HTTP_2 preference sends an h2c
        // Upgrade request over plaintext that uvicorn/h11 rejects with 400 Bad Request
        // ("Unsupported upgrade request"), which the ai-service never even sees as a
        // routed request.
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(orDefault(connectTimeout, Duration.ofSeconds(5)))
                .followRedirects(HttpClient.Redirect.NEVER)
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(orDefault(readTimeout, Duration.ofSeconds(30)));
        return RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .build();
    }

    private static Duration orDefault(Duration value, Duration fallback) {
        return value == null || value.isZero() || value.isNegative() ? fallback : value;
    }
}
