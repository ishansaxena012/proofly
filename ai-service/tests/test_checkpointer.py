"""Redis-backed checkpointing: persistence, resume, and graceful degradation."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from app.graph.budget import ResearchBudget
from app.graph.checkpointer import RedisCheckpointSaver, build_checkpointer
from app.graph.context import JobContext
from app.graph.pipeline import build_graph
from app.graph.state import initial_state


class FakeRedis:
    """Minimal async stand-in for the handful of commands the saver uses."""

    def __init__(self, *, fail: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.fail = fail
        self.writes = 0

    async def get(self, key: str):
        if self.fail:
            raise ConnectionError("redis is down")
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        if self.fail:
            raise ConnectionError("redis is down")
        self.writes += 1
        self.store[key] = value

    async def delete(self, key: str):
        if self.fail:
            raise ConnectionError("redis is down")
        self.store.pop(key, None)

    async def aclose(self):
        return None


def _context(settings, providers, backend, job_id: str) -> JobContext:
    return JobContext.create(
        job_id=job_id,
        product_query="Sony WH-1000XM6",
        demo_mode=True,
        settings=settings,
        providers=providers,
        backend=backend,
        budget=ResearchBudget(settings),
    )


def test_build_checkpointer_falls_back_to_memory_without_a_url():
    assert isinstance(build_checkpointer(""), InMemorySaver)
    assert isinstance(build_checkpointer("redis://localhost:6379/0"), RedisCheckpointSaver)


async def test_a_run_is_persisted_and_can_be_resumed_from_redis(
    settings, providers, backend
):
    redis = FakeRedis()
    job_id = "checkpoint-job"
    saver = RedisCheckpointSaver("redis://ignored", client=redis)

    ctx = _context(settings, providers, backend, job_id)
    graph = build_graph(ctx, checkpointer=saver)
    await graph.ainvoke(
        initial_state(job_id, "Sony WH-1000XM6", True),
        config={"configurable": {"thread_id": job_id}, "recursion_limit": 60},
    )

    key = f"proofly:langgraph:checkpoint:{job_id}"
    assert key in redis.store
    assert redis.writes > 1

    # A fresh saver (as after a crash and restart) recovers the thread's state.
    resumed = RedisCheckpointSaver("redis://ignored", client=redis)
    tuple_ = await resumed.aget_tuple({"configurable": {"thread_id": job_id, "checkpoint_ns": ""}})
    assert tuple_ is not None
    channels = tuple_.checkpoint["channel_values"]
    assert channels["terminal_status"] == "COMPLETED"
    assert channels["report"] is not None
    assert len(channels["evidence"]) > 0


async def test_a_second_run_of_the_same_job_reuses_the_checkpoint(
    settings, providers, backend, backend_calls
):
    redis = FakeRedis()
    job_id = "resume-job"

    ctx = _context(settings, providers, backend, job_id)
    await build_graph(ctx, checkpointer=RedisCheckpointSaver("redis://x", client=redis)).ainvoke(
        initial_state(job_id, "Sony WH-1000XM6", True),
        config={"configurable": {"thread_id": job_id}, "recursion_limit": 60},
    )
    calls_after_first = len(backend_calls)

    # Re-invoking the same thread id resumes from the stored checkpoint instead
    # of redoing the expensive research.
    ctx2 = _context(settings, providers, backend, job_id)
    resumed = await build_graph(
        ctx2, checkpointer=RedisCheckpointSaver("redis://x", client=redis)
    ).ainvoke(None, config={"configurable": {"thread_id": job_id}, "recursion_limit": 60})

    assert resumed["terminal_status"] == "COMPLETED"
    assert len(backend_calls) == calls_after_first, "resume must not repeat the research"


async def test_unreachable_redis_degrades_to_in_memory(settings, providers, backend):
    redis = FakeRedis(fail=True)
    job_id = "degraded-job"
    saver = RedisCheckpointSaver("redis://ignored", client=redis)

    ctx = _context(settings, providers, backend, job_id)
    state = await build_graph(ctx, checkpointer=saver).ainvoke(
        initial_state(job_id, "Sony WH-1000XM6", True),
        config={"configurable": {"thread_id": job_id}, "recursion_limit": 60},
    )

    assert state["terminal_status"] == "COMPLETED"
    assert redis.store == {}


async def test_deleting_a_thread_clears_redis(settings, providers, backend):
    redis = FakeRedis()
    job_id = "delete-job"
    saver = RedisCheckpointSaver("redis://ignored", client=redis)
    ctx = _context(settings, providers, backend, job_id)
    await build_graph(ctx, checkpointer=saver).ainvoke(
        initial_state(job_id, "Sony WH-1000XM6", True),
        config={"configurable": {"thread_id": job_id}, "recursion_limit": 60},
    )
    assert redis.store

    await saver.adelete_thread(job_id)
    assert redis.store == {}
