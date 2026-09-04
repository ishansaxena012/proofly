package com.proofly.backend.sse;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.TestFixtures;
import com.proofly.backend.api.dto.ResearchEventDto;
import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.domain.ResearchEventType;
import com.proofly.backend.domain.ResearchJobStatus;
import com.proofly.backend.service.ResearchEventService;
import com.proofly.backend.service.ResearchJobService;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.data.redis.listener.Topic;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class ResearchEventStreamServiceTest {

    private static final UUID JOB = UUID.fromString("dddd1111-2222-3333-4444-555555555555");
    private static final UUID USER = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Mock private ResearchJobService jobService;
    @Mock private ResearchEventService eventService;
    @Mock private RedisMessageListenerContainer listenerContainer;

    private ResearchEventStreamService service;

    @BeforeEach
    void setUp() {
        service = new ResearchEventStreamService(jobService, eventService, listenerContainer,
                new ObjectMapper(), TestFixtures.properties());
        when(eventService.history(JOB)).thenReturn(List.of());
    }

    private ResearchEventDto event(ResearchEventType type, String message) {
        return new ResearchEventDto(UUID.randomUUID(), type, message, null, OffsetDateTime.now());
    }

    @Test
    void enforcesOwnershipBeforeOpeningAStream() {
        when(jobService.requireOwnedJob(JOB)).thenThrow(ApiException.notFound("Research job was not found"));

        assertThatThrownBy(() -> service.subscribe(JOB)).isInstanceOf(ApiException.class);
        verify(listenerContainer, never()).addMessageListener(any(), any(Topic.class));
    }

    @Test
    void subscribesToTheJobsRedisChannel() {
        when(jobService.requireOwnedJob(JOB))
                .thenReturn(TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.RESEARCHING));

        SseEmitter emitter = service.subscribe(JOB);

        assertThat(emitter).isNotNull();
        ArgumentCaptor<Topic> topic = ArgumentCaptor.forClass(Topic.class);
        verify(listenerContainer).addMessageListener(any(MessageListener.class), topic.capture());
        assertThat(topic.getValue()).isInstanceOf(ChannelTopic.class);
        assertThat(topic.getValue().getTopic()).isEqualTo("proofly:events:" + JOB);
    }

    @Test
    void replaysThePersistedLogBeforeGoingLive() {
        when(jobService.requireOwnedJob(JOB))
                .thenReturn(TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.RESEARCHING));
        when(eventService.history(JOB)).thenReturn(List.of(
                event(ResearchEventType.PRODUCT_IDENTIFIED, "Identified product"),
                event(ResearchEventType.RESEARCH_STARTED, "Research started")));

        service.subscribe(JOB);

        // Read once for the replay and once more after subscribing, so an event published
        // in between cannot be lost.
        verify(eventService, times(2)).history(JOB);
    }

    @Test
    void keepsTheStreamOpenWhileTheJobIsStillRunning() {
        when(jobService.requireOwnedJob(JOB))
                .thenReturn(TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.VERIFYING));

        service.subscribe(JOB);

        verify(listenerContainer, never()).removeMessageListener(any(), any(Topic.class));
    }

    @Test
    void closesImmediatelyForAJobThatHasAlreadyFinished() {
        when(jobService.requireOwnedJob(JOB))
                .thenReturn(TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.COMPLETED));
        when(eventService.history(JOB)).thenReturn(List.of(
                event(ResearchEventType.REPORT_COMPLETED, "Report ready")));

        service.subscribe(JOB);

        verify(listenerContainer).removeMessageListener(any(MessageListener.class), any(Topic.class));
    }

    @Test
    void closesImmediatelyForAFailedJobToo() {
        when(jobService.requireOwnedJob(JOB))
                .thenReturn(TestFixtures.job(JOB, USER, UUID.randomUUID(), ResearchJobStatus.FAILED));

        service.subscribe(JOB);

        verify(listenerContainer).removeMessageListener(any(MessageListener.class), any(Topic.class));
    }
}
