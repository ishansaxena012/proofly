package com.proofly.backend.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.TestFixtures;
import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;

class InternalApiKeyFilterTest {

    /** Matches the application's Jackson setup, which registers the JSR-310 module. */
    private final ObjectMapper objectMapper = Jackson2ObjectMapperBuilder.json().build();

    private final InternalApiKeyFilter filter =
            new InternalApiKeyFilter(TestFixtures.properties(), objectMapper);

    @AfterEach
    void clearContext() {
        SecurityContextHolder.clearContext();
    }

    private MockHttpServletResponse callWith(String key, FilterChain chain) throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/internal/v1/research/x/status");
        if (key != null) {
            request.addHeader(InternalApiKeyFilter.HEADER, key);
        }
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, chain);
        return response;
    }

    @Test
    void letsTheAiServiceThroughWithTheRightKey() throws Exception {
        FilterChain chain = Mockito.mock(FilterChain.class);

        MockHttpServletResponse response = callWith(TestFixtures.INTERNAL_KEY, chain);

        Mockito.verify(chain).doFilter(Mockito.any(), Mockito.any());
        assertThat(response.getStatus()).isEqualTo(200);
    }

    @Test
    void rejectsAMissingKeyWith403AndTheContractErrorShape() throws Exception {
        FilterChain chain = Mockito.mock(FilterChain.class);

        MockHttpServletResponse response = callWith(null, chain);

        Mockito.verifyNoInteractions(chain);
        assertThat(response.getStatus()).isEqualTo(403);
        assertThat(response.getContentAsString()).contains("\"errorCode\":\"FORBIDDEN\"");
    }

    @Test
    void rejectsAWrongKey() throws Exception {
        FilterChain chain = Mockito.mock(FilterChain.class);

        MockHttpServletResponse response = callWith("not-the-key", chain);

        Mockito.verifyNoInteractions(chain);
        assertThat(response.getStatus()).isEqualTo(403);
    }

    @Test
    void grantsTheInternalServiceRoleForTheDurationOfTheRequestOnly() throws Exception {
        FilterChain chain = (request, response) -> {
            var authentication = SecurityContextHolder.getContext().getAuthentication();
            assertThat(authentication).isNotNull();
            assertThat(authentication.getAuthorities())
                    .anySatisfy(authority -> assertThat(authority.getAuthority())
                            .isEqualTo(InternalApiKeyFilter.ROLE));
        };

        callWith(TestFixtures.INTERNAL_KEY, chain);

        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
    }
}
