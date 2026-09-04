package com.proofly.backend.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    public static final String BEARER_SCHEME = "bearerAuth";
    public static final String INTERNAL_SCHEME = "internalApiKey";

    @Bean
    public OpenAPI prooflyOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("Proofly API")
                        .version("v1")
                        .description("""
                                Public REST + SSE API for the Proofly product research agent, plus the
                                internal callback API the Python AI service uses to push results back.

                                Authentication: send `Authorization: Bearer <supabase-jwt>`. When the
                                backend is started without `JWT_ISSUER_URI` it runs in dev-auth mode and
                                accepts `Authorization: Bearer dev-{userId}` where `{userId}` is a UUID.

                                Internal endpoints under `/internal/v1` require the
                                `X-Internal-Key` header instead.""")
                        .license(new License().name("Proofly capstone")))
                .components(new Components()
                        .addSecuritySchemes(BEARER_SCHEME, new SecurityScheme()
                                .type(SecurityScheme.Type.HTTP)
                                .scheme("bearer")
                                .bearerFormat("JWT"))
                        .addSecuritySchemes(INTERNAL_SCHEME, new SecurityScheme()
                                .type(SecurityScheme.Type.APIKEY)
                                .in(SecurityScheme.In.HEADER)
                                .name("X-Internal-Key")))
                .addSecurityItem(new SecurityRequirement().addList(BEARER_SCHEME));
    }
}
