package com.proofly.backend.config;

import java.util.concurrent.Executors;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;

@Configuration
public class RedisConfig {

    /**
     * Fan-out for SSE. The container is shared: each open {@code SseEmitter} registers a
     * listener on {@code proofly:events:{jobId}} and removes it on completion, so a single
     * Redis subscription connection serves every browser tab.
     *
     * <p>It deliberately holds no listeners at startup, which means no Redis connection is
     * opened until the first SSE subscriber arrives.
     */
    @Bean(destroyMethod = "destroy")
    public RedisMessageListenerContainer redisMessageListenerContainer(RedisConnectionFactory connectionFactory) {
        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);
        container.setTaskExecutor(Executors.newVirtualThreadPerTaskExecutor());
        container.setSubscriptionExecutor(Executors.newVirtualThreadPerTaskExecutor());
        return container;
    }
}
