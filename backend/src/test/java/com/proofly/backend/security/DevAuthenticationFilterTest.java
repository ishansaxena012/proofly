package com.proofly.backend.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.proofly.backend.TestFixtures;
import com.proofly.backend.service.UserProvisioningService;
import jakarta.servlet.FilterChain;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;

class DevAuthenticationFilterTest {

    private final UserProvisioningService userProvisioning = Mockito.mock(UserProvisioningService.class);
    private final DevAuthenticationFilter filter =
            new DevAuthenticationFilter(TestFixtures.properties(), provider(userProvisioning));

    @SuppressWarnings("unchecked")
    private static ObjectProvider<UserProvisioningService> provider(UserProvisioningService service) {
        ObjectProvider<UserProvisioningService> provider = Mockito.mock(ObjectProvider.class);
        Mockito.when(provider.getIfAvailable()).thenReturn(service);
        return provider;
    }

    @AfterEach
    void clearContext() {
        SecurityContextHolder.clearContext();
    }

    private ProoflyPrincipal authenticate(MockHttpServletRequest request) throws Exception {
        FilterChain chain = Mockito.mock(FilterChain.class);
        filter.doFilter(request, new MockHttpServletResponse(), chain);
        Mockito.verify(chain).doFilter(Mockito.any(), Mockito.any());

        var authentication = SecurityContextHolder.getContext().getAuthentication();
        return authentication == null ? null : (ProoflyPrincipal) authentication.getPrincipal();
    }

    private ProoflyPrincipal authenticateWith(String authorizationHeader) throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/research");
        if (authorizationHeader != null) {
            request.addHeader("Authorization", authorizationHeader);
        }
        return authenticate(request);
    }

    @Test
    void mapsADevTokenStraightOntoAUserId() throws Exception {
        UUID userId = UUID.randomUUID();

        ProoflyPrincipal principal = authenticateWith("Bearer dev-" + userId);

        assertThat(principal).isNotNull();
        assertThat(principal.userId()).isEqualTo(userId);
        assertThat(principal.devAuth()).isTrue();
        assertThat(principal.email()).isEqualTo(userId + "@dev.proofly.local");
    }

    @Test
    void provisionsTheUsersRowOnFirstSightOfAnUnknownDevId() throws Exception {
        UUID userId = UUID.randomUUID();

        authenticateWith("Bearer dev-" + userId);
        SecurityContextHolder.clearContext();
        authenticateWith("Bearer dev-" + userId);

        // Provisioned once, then remembered — not one write per request.
        Mockito.verify(userProvisioning, Mockito.times(1))
                .ensureUser(Mockito.argThat(principal -> principal.userId().equals(userId)));
    }

    @Test
    void aProvisioningFailureDoesNotBreakAuthentication() throws Exception {
        Mockito.doThrow(new IllegalStateException("database down"))
                .when(userProvisioning).ensureUser(Mockito.any());
        UUID userId = UUID.randomUUID();

        ProoflyPrincipal principal = authenticateWith("Bearer dev-" + userId);

        assertThat(principal).isNotNull();
        assertThat(principal.userId()).isEqualTo(userId);
    }

    @Test
    void acceptsTheAccessTokenQueryParameterOnTheSseEndpoint() throws Exception {
        UUID userId = UUID.randomUUID();
        MockHttpServletRequest request =
                new MockHttpServletRequest("GET", "/api/v1/research/" + UUID.randomUUID() + "/events");
        request.setParameter("access_token", "dev-" + userId);

        ProoflyPrincipal principal = authenticate(request);

        assertThat(principal).isNotNull();
        assertThat(principal.userId()).isEqualTo(userId);
    }

    @Test
    void ignoresTheAccessTokenQueryParameterOnEveryOtherRoute() throws Exception {
        MockHttpServletRequest request =
                new MockHttpServletRequest("GET", "/api/v1/research/" + UUID.randomUUID());
        request.setParameter("access_token", "dev-" + UUID.randomUUID());

        assertThat(authenticate(request)).isNull();
    }

    @Test
    void ignoresTheAccessTokenQueryParameterOnANonGetRequest() throws Exception {
        MockHttpServletRequest request =
                new MockHttpServletRequest("POST", "/api/v1/research/" + UUID.randomUUID() + "/events");
        request.setParameter("access_token", "dev-" + UUID.randomUUID());

        assertThat(authenticate(request)).isNull();
    }

    @Test
    void ignoresATokenWhoseUserIdIsNotAUuid() throws Exception {
        assertThat(authenticateWith("Bearer dev-not-a-uuid")).isNull();
    }

    @Test
    void ignoresNonDevBearerTokens() throws Exception {
        assertThat(authenticateWith("Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature")).isNull();
    }

    @Test
    void ignoresRequestsWithNoAuthorizationHeader() throws Exception {
        assertThat(authenticateWith(null)).isNull();
    }

    @Test
    void ignoresNonBearerSchemes() throws Exception {
        assertThat(authenticateWith("Basic ZGV2OmRldg==")).isNull();
    }
}
