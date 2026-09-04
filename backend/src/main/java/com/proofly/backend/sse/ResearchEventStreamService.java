package com.proofly.backend.sse;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.proofly.backend.api.dto.ResearchEventDto;
import com.proofly.backend.config.ProoflyProperties;
import com.proofly.backend.domain.ResearchJob;
import com.proofly.backend.service.ResearchEventService;
import com.proofly.backend.service.ResearchJobService;
import java.io.IOException;
import java.time.Duration;
import java.util.List;
import java.util.Queue;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * Serves {@code GET /api/v1/research/{id}/events}.
 *
 * <p>Each subscriber gets the full history before anything live, so a refresh or a late
 * join never shows a partial timeline. The ordering is: subscribe to Redis first, then
 * replay the persisted log, then release the buffered live messages — buffering while
 * replaying is what stops an event that lands mid-replay from being dropped or delivered
 * out of order. Events are de-duplicated on their database id, so the overlap between the
 * replay and the live feed is invisible to the client.
 */
@Service
public class ResearchEventStreamService {

    private static final Logger log = LoggerFactory.getLogger(ResearchEventStreamService.class);

    private final ResearchJobService jobService;
    private final ResearchEventService eventService;
    private final RedisMessageListenerContainer listenerContainer;
    private final ObjectMapper objectMapper;
    private final ProoflyProperties properties;
    private final ScheduledExecutorService heartbeats =
            Executors.newSingleThreadScheduledExecutor(runnable -> {
                Thread thread = new Thread(runnable, "proofly-sse-heartbeat");
                thread.setDaemon(true);
                return thread;
            });

    public ResearchEventStreamService(ResearchJobService jobService,
                                      ResearchEventService eventService,
                                      RedisMessageListenerContainer listenerContainer,
                                      ObjectMapper objectMapper,
                                      ProoflyProperties properties) {
        this.jobService = jobService;
        this.eventService = eventService;
        this.listenerContainer = listenerContainer;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    /** Ownership is enforced here: a job the caller does not own is reported as 404. */
    public SseEmitter subscribe(UUID researchJobId) {
        ResearchJob job = jobService.requireOwnedJob(researchJobId);

        Duration timeout = properties.research().sseTimeout();
        SseEmitter emitter = new SseEmitter(timeout == null ? 900_000L : timeout.toMillis());
        Subscription subscription = new Subscription(researchJobId, emitter);

        ChannelTopic topic = new ChannelTopic(properties.research().eventChannel(researchJobId));
        listenerContainer.addMessageListener(subscription, topic);

        ScheduledFuture<?> heartbeat = scheduleHeartbeat(subscription);
        Runnable cleanup = () -> {
            heartbeat.cancel(false);
            listenerContainer.removeMessageListener(subscription, topic);
            subscription.closed.set(true);
        };
        emitter.onCompletion(cleanup);
        emitter.onTimeout(() -> {
            cleanup.run();
            emitter.complete();
        });
        emitter.onError(error -> cleanup.run());

        try {
            subscription.replay(eventService.history(researchJobId));
            subscription.goLive(eventService.history(researchJobId));
        } catch (IOException ex) {
            log.debug("SSE client for job {} disconnected during replay", researchJobId);
            cleanup.run();
            emitter.completeWithError(ex);
            return emitter;
        }

        if (job.getStatus().isTerminal()) {
            // Nothing more will ever be published for this job; close cleanly rather than
            // holding an idle connection open until the timeout.
            cleanup.run();
            emitter.complete();
        }
        return emitter;
    }

    private ScheduledFuture<?> scheduleHeartbeat(Subscription subscription) {
        Duration interval = properties.research().sseHeartbeatInterval();
        long millis = (interval == null ? Duration.ofSeconds(20) : interval).toMillis();
        return heartbeats.scheduleAtFixedRate(subscription::heartbeat, millis, millis, TimeUnit.MILLISECONDS);
    }

    @PreDestroy
    public void shutdown() {
        heartbeats.shutdownNow();
    }

    /** One open SSE stream, and the Redis listener feeding it. */
    private final class Subscription implements MessageListener {

        private final UUID researchJobId;
        private final SseEmitter emitter;
        private final Set<UUID> delivered = ConcurrentHashMap.newKeySet();
        private final Queue<ResearchEventDto> pending = new ConcurrentLinkedQueue<>();
        private final AtomicBoolean live = new AtomicBoolean(false);
        private final AtomicBoolean closed = new AtomicBoolean(false);

        private Subscription(UUID researchJobId, SseEmitter emitter) {
            this.researchJobId = researchJobId;
            this.emitter = emitter;
        }

        @Override
        public void onMessage(Message message, byte[] pattern) {
            if (closed.get()) {
                return;
            }
            ResearchEventDto event;
            try {
                event = objectMapper.readValue(message.getBody(), ResearchEventDto.class);
            } catch (IOException ex) {
                log.warn("Ignoring unreadable event on the channel for job {}", researchJobId, ex);
                return;
            }
            if (!live.get()) {
                pending.add(event);
                return;
            }
            try {
                send(event);
            } catch (IOException ex) {
                log.debug("SSE client for job {} went away", researchJobId);
                closed.set(true);
                emitter.completeWithError(ex);
            }
        }

        private void replay(List<ResearchEventDto> history) throws IOException {
            for (ResearchEventDto event : history) {
                send(event);
            }
        }

        /**
         * Switches to live delivery. The second history read closes the gap where an event
         * could have been persisted and published in between subscribing and replaying.
         */
        private void goLive(List<ResearchEventDto> historyAfterSubscribe) throws IOException {
            for (ResearchEventDto event : historyAfterSubscribe) {
                send(event);
            }
            live.set(true);
            ResearchEventDto buffered;
            while ((buffered = pending.poll()) != null) {
                send(buffered);
            }
        }

        private synchronized void send(ResearchEventDto event) throws IOException {
            if (closed.get() || event == null || event.id() == null || !delivered.add(event.id())) {
                return;
            }
            emitter.send(SseEmitter.event()
                    .id(event.id().toString())
                    .name(event.eventType().name())
                    .data(event));
        }

        private void heartbeat() {
            if (closed.get()) {
                return;
            }
            try {
                synchronized (this) {
                    emitter.send(SseEmitter.event().comment("keep-alive"));
                }
            } catch (Exception ex) {
                closed.set(true);
                emitter.complete();
            }
        }
    }
}
