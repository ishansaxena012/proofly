package com.proofly.backend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.proofly.backend.api.error.ApiException;
import com.proofly.backend.api.error.ErrorCode;
import com.proofly.backend.domain.ResearchJobStatus;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class ResearchJobStateMachineTest {

    private final ResearchJobStateMachine stateMachine = new ResearchJobStateMachine();

    @Test
    void allowsTheHappyPathInOrder() {
        ResearchJobStatus[] path = {
                ResearchJobStatus.CREATED, ResearchJobStatus.QUEUED, ResearchJobStatus.RUNNING,
                ResearchJobStatus.IDENTIFYING_PRODUCT, ResearchJobStatus.PLANNING_RESEARCH,
                ResearchJobStatus.RESEARCHING, ResearchJobStatus.EXTRACTING_EVIDENCE,
                ResearchJobStatus.ANALYZING, ResearchJobStatus.VERIFYING,
                ResearchJobStatus.GENERATING_REPORT, ResearchJobStatus.COMPLETED};

        for (int i = 0; i < path.length - 1; i++) {
            assertThat(stateMachine.canTransition(path[i], path[i + 1]))
                    .as("%s -> %s", path[i], path[i + 1])
                    .isTrue();
        }
    }

    @Test
    void allowsSkippingStages() {
        assertThat(stateMachine.canTransition(ResearchJobStatus.RUNNING, ResearchJobStatus.RESEARCHING)).isTrue();
        assertThat(stateMachine.canTransition(ResearchJobStatus.QUEUED, ResearchJobStatus.GENERATING_REPORT)).isTrue();
    }

    @Test
    void rejectsGoingBackwards() {
        assertThat(stateMachine.canTransition(ResearchJobStatus.VERIFYING, ResearchJobStatus.RESEARCHING)).isFalse();
        assertThat(stateMachine.canTransition(ResearchJobStatus.RUNNING, ResearchJobStatus.QUEUED)).isFalse();
    }

    @Test
    void treatsRepeatedStatusAsIdempotent() {
        assertThat(stateMachine.canTransition(ResearchJobStatus.RESEARCHING, ResearchJobStatus.RESEARCHING)).isTrue();
        assertThat(stateMachine.canTransition(ResearchJobStatus.COMPLETED, ResearchJobStatus.COMPLETED)).isTrue();
    }

    @ParameterizedTest
    @EnumSource(value = ResearchJobStatus.class,
            names = {"COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED"})
    void neverLeavesATerminalState(ResearchJobStatus terminal) {
        assertThat(terminal.isTerminal()).isTrue();
        for (ResearchJobStatus target : ResearchJobStatus.values()) {
            assertThat(stateMachine.canTransition(terminal, target))
                    .as("%s -> %s", terminal, target)
                    // Re-asserting the same terminal state stays allowed so that a retried
                    // callback is idempotent; moving anywhere else is not.
                    .isEqualTo(target == terminal);
        }
    }

    @ParameterizedTest
    @EnumSource(value = ResearchJobStatus.class,
            names = {"CREATED", "QUEUED", "RUNNING", "RESEARCHING", "VERIFYING", "GENERATING_REPORT"})
    void allowsFailingFromAnyLiveState(ResearchJobStatus live) {
        assertThat(stateMachine.canTransition(live, ResearchJobStatus.FAILED)).isTrue();
        assertThat(stateMachine.canTransition(live, ResearchJobStatus.CANCELLED)).isTrue();
        assertThat(stateMachine.canTransition(live, ResearchJobStatus.PARTIALLY_COMPLETED)).isTrue();
    }

    @Test
    void requireTransitionRaisesAValidationError() {
        assertThatThrownBy(() -> stateMachine.requireTransition(
                ResearchJobStatus.COMPLETED, ResearchJobStatus.RUNNING))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getErrorCode())
                .isEqualTo(ErrorCode.VALIDATION_ERROR);
    }

    @Test
    void onlyCompletedAndPartiallyCompletedExposeAReport() {
        assertThat(ResearchJobStatus.COMPLETED.isReportAvailable()).isTrue();
        assertThat(ResearchJobStatus.PARTIALLY_COMPLETED.isReportAvailable()).isTrue();
        assertThat(ResearchJobStatus.FAILED.isReportAvailable()).isFalse();
        assertThat(ResearchJobStatus.RESEARCHING.isReportAvailable()).isFalse();
    }
}
