package com.proofly.backend;

import com.proofly.backend.config.ProoflyProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableConfigurationProperties(ProoflyProperties.class)
@EnableScheduling
public class ProoflyBackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(ProoflyBackendApplication.class, args);
    }
}
