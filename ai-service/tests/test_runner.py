"""Background job execution, cancellation and failure reporting."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.models.enums import ErrorCode, JobStatus
from app.services import runner as runner_module
from app.services.backend_client import BackendClient
from app.services.runner import ResearchJobRunner


@pytest.fixture
def patched_backend(monkeypatch, settings):
    calls: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append({"path": request.url.path, "json": json.loads(request.content or b"{}")})
        return httpx.Response(200, json={"ok": True})

    def factory(_settings, client=None):
        return BackendClient(
            _settings,
            client=httpx.AsyncClient(
                base_url=_settings.backend_internal_url,
                transport=httpx.MockTransport(handler),
                headers={"X-Internal-Key": _settings.internal_api_key},
            ),
        )

    monkeypatch.setattr(runner_module, "BackendClient", factory)
    return calls


async def test_a_job_runs_to_completion(settings, patched_backend):
    job_runner = ResearchJobRunner(settings)
    result = await job_runner.run("runner-job", "Sony WH-1000XM6", True)

    assert result is not None
    assert result["terminal_status"] == JobStatus.COMPLETED.value
    statuses = [c["json"]["status"] for c in patched_backend if c["path"].endswith("/status")]
    assert statuses[0] == JobStatus.RUNNING.value
    assert statuses[-1] == JobStatus.COMPLETED.value
    await job_runner.shutdown()


async def test_start_schedules_a_background_task_and_refuses_duplicates(settings, patched_backend):
    job_runner = ResearchJobRunner(settings)
    assert job_runner.start("bg-job", "Sony WH-1000XM6", True) is True
    assert job_runner.is_running("bg-job") is True
    assert job_runner.start("bg-job", "Sony WH-1000XM6", True) is False

    await asyncio.sleep(0)
    await job_runner.shutdown()
    assert job_runner.active_jobs == []


async def test_cancelling_a_job_reports_cancelled(settings, patched_backend, monkeypatch):
    started = asyncio.Event()

    class SlowGraph:
        async def ainvoke(self, *args, **kwargs):
            started.set()
            await asyncio.sleep(60)

    monkeypatch.setattr(runner_module, "build_graph", lambda *a, **k: SlowGraph())

    job_runner = ResearchJobRunner(settings)
    job_runner.start("cancel-job", "Sony WH-1000XM6", True)
    await asyncio.wait_for(started.wait(), timeout=5)

    assert job_runner.cancel("cancel-job") is True
    await asyncio.sleep(0.05)

    statuses = [c["json"] for c in patched_backend if c["path"].endswith("/status")]
    assert any(entry["status"] == JobStatus.CANCELLED.value for entry in statuses)
    assert job_runner.cancel("cancel-job") is False
    await job_runner.shutdown()


async def test_an_ambiguous_query_fails_the_job_with_invalid_product(settings, patched_backend):
    job_runner = ResearchJobRunner(settings)
    result = await job_runner.run("ambiguous-job", "best Sony headphones", True)

    assert result["error_code"] == ErrorCode.INVALID_PRODUCT.value
    statuses = [c["json"] for c in patched_backend if c["path"].endswith("/status")]
    assert statuses[-1]["status"] == JobStatus.FAILED.value
    assert statuses[-1]["errorCode"] == ErrorCode.INVALID_PRODUCT.value
    await job_runner.shutdown()


async def test_an_unexpected_crash_is_reported_not_raised(settings, patched_backend, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("graph construction failed")

    monkeypatch.setattr(runner_module, "build_graph", explode)
    job_runner = ResearchJobRunner(settings)
    assert await job_runner.run("broken-job", "Sony WH-1000XM6", True) is None

    statuses = [c["json"] for c in patched_backend if c["path"].endswith("/status")]
    assert statuses[-1]["status"] == JobStatus.FAILED.value
    assert statuses[-1]["errorCode"] == ErrorCode.AGENT_FAILURE.value
    await job_runner.shutdown()


async def test_backend_callback_failures_do_not_kill_the_job(settings, monkeypatch):
    async def always_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "backend down"})

    def factory(_settings, client=None):
        return BackendClient(
            _settings,
            client=httpx.AsyncClient(
                base_url=_settings.backend_internal_url,
                transport=httpx.MockTransport(always_500),
            ),
        )

    monkeypatch.setattr(runner_module, "BackendClient", factory)
    job_runner = ResearchJobRunner(settings)
    result = await job_runner.run("resilient-job", "Sony WH-1000XM6", True)

    assert result["terminal_status"] == JobStatus.COMPLETED.value
    assert result["report"] is not None
    await job_runner.shutdown()
