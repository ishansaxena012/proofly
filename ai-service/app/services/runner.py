"""Job runner: owns the asyncio tasks that execute research graphs."""

from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.graph.budget import BudgetExceeded, ResearchBudget
from app.graph.checkpointer import build_checkpointer
from app.graph.context import JobContext
from app.graph.pipeline import build_graph
from app.graph.state import initial_state
from app.models.enums import ErrorCode, EventType, JobStatus
from app.providers.factory import ProviderBundle, build_providers
from app.services.backend_client import BackendClient

log = logging.getLogger(__name__)

FINALISATION_GRACE_SECONDS = 15
RECURSION_LIMIT = 60


class ResearchJobRunner:
    """Starts, tracks and cancels background research jobs."""

    def __init__(self, settings: Settings, checkpointer=None) -> None:
        self._settings = settings
        self._checkpointer = checkpointer or build_checkpointer(settings.redis_url)
        self._tasks: dict[str, asyncio.Task] = {}

    # ── lifecycle ──────────────────────────────────────────────────────────

    @property
    def active_jobs(self) -> list[str]:
        return [job_id for job_id, task in self._tasks.items() if not task.done()]

    def is_running(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        return task is not None and not task.done()

    def start(self, job_id: str, product_query: str, demo_mode: bool) -> bool:
        """Schedule a job. Returns False if the same job is already running."""

        if self.is_running(job_id):
            log.info("job %s is already running; ignoring duplicate execute", job_id)
            return False
        task = asyncio.create_task(
            self.run(job_id, product_query, demo_mode), name=f"research-{job_id}"
        )
        self._tasks[job_id] = task
        task.add_done_callback(lambda finished: self._tasks.pop(job_id, None))
        return True

    def cancel(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def shutdown(self) -> None:
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        closer = getattr(self._checkpointer, "aclose", None)
        if closer is not None:
            await closer()

    # ── execution ──────────────────────────────────────────────────────────

    async def run(self, job_id: str, product_query: str, demo_mode: bool) -> dict | None:
        settings = self._settings
        demo = bool(demo_mode) or settings.demo_mode
        providers: ProviderBundle | None = None
        backend = BackendClient(settings)
        try:
            providers = build_providers(settings, demo_mode=demo)
            budget = ResearchBudget(settings)
            ctx = JobContext.create(
                job_id=job_id,
                product_query=product_query,
                demo_mode=demo,
                settings=settings,
                providers=providers,
                backend=backend,
                budget=budget,
            )
            graph = build_graph(ctx, checkpointer=self._checkpointer)

            await backend.post_status(job_id, JobStatus.RUNNING)
            log.info(
                "job %s started (demo=%s, llm=%s, search=%s)",
                job_id, demo, providers.llm.name, providers.search.name,
            )
            result = await asyncio.wait_for(
                graph.ainvoke(
                    initial_state(job_id, product_query, demo),
                    config={
                        "configurable": {"thread_id": job_id},
                        "recursion_limit": RECURSION_LIMIT,
                    },
                ),
                timeout=settings.research_max_duration_seconds + FINALISATION_GRACE_SECONDS,
            )
            log.info("job %s finished with status %s", job_id, result.get("terminal_status"))
            return result
        except asyncio.CancelledError:
            log.info("job %s cancelled", job_id)
            await backend.post_event(
                job_id, EventType.JOB_FAILED, "Research job was cancelled.", {"cancelled": True}
            )
            await backend.post_status(
                job_id,
                JobStatus.CANCELLED,
                current_stage=JobStatus.CANCELLED.value,
                error_code=None,
                error_message="Job cancelled by request.",
            )
            raise
        except (TimeoutError, BudgetExceeded) as exc:
            message = f"Research job exceeded its time budget: {exc}"
            log.warning("job %s timed out: %s", job_id, exc)
            await self._fail(backend, job_id, ErrorCode.TIMEOUT, message)
        except Exception as exc:  # noqa: BLE001 - report, never crash the service
            message = f"Research job failed: {type(exc).__name__}: {exc}"
            log.exception("job %s failed", job_id)
            await self._fail(backend, job_id, ErrorCode.AGENT_FAILURE, message)
        finally:
            if providers is not None:
                await providers.aclose()
            await backend.aclose()
        return None

    async def _fail(
        self, backend: BackendClient, job_id: str, code: ErrorCode, message: str
    ) -> None:
        await backend.post_event(
            job_id, EventType.JOB_FAILED, message, {"errorCode": code.value}
        )
        await backend.post_status(
            job_id,
            JobStatus.FAILED,
            current_stage=JobStatus.FAILED.value,
            error_code=code.value,
            error_message=message,
        )
