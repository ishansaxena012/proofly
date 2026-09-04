"""Redis-backed LangGraph checkpointing, keyed by research job id.

Why this rather than ``langgraph.checkpoint.redis.AsyncRedisSaver``: that saver is
built on RediSearch indices (via redisvl), and the Redis in ``docker-compose.yml``
is plain ``redis:7-alpine``, which has no search module. This saver keeps
LangGraph's own in-memory checkpoint semantics — so behaviour is exactly what the
library expects — and mirrors each thread's checkpoint state into a single plain
Redis key after every write. That works on stock Redis, survives a process
crash, and lets a re-run of the same job id resume from the last completed node
instead of repeating expensive research.

If Redis is unreachable the saver logs once and degrades to pure in-memory
checkpointing; the job still runs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata
from langgraph.checkpoint.memory import InMemorySaver

log = logging.getLogger(__name__)

KEY_PREFIX = "proofly:langgraph:checkpoint"
DEFAULT_TTL_SECONDS = 7 * 24 * 3600


def _encode_blob(blob: tuple[str, bytes]) -> list:
    type_name, data = blob
    return [type_name, base64.b64encode(data or b"").decode("ascii")]


def _decode_blob(payload: list) -> tuple[str, bytes]:
    return payload[0], base64.b64decode(payload[1].encode("ascii"))


class RedisCheckpointSaver(InMemorySaver):
    """In-memory checkpoint semantics, mirrored into a plain Redis key per job."""

    def __init__(
        self,
        redis_url: str,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        client: Any | None = None,
    ) -> None:
        super().__init__()
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._client = client
        self._client_ready = client is not None
        self._healthy = True
        self._loaded: set[str] = set()
        self._lock = asyncio.Lock()

    # ── redis plumbing ────────────────────────────────────────────────────

    async def _redis(self):
        if self._client_ready:
            return self._client
        try:
            import redis.asyncio as redis_asyncio  # noqa: PLC0415 - optional at import time

            self._client = redis_asyncio.from_url(self._redis_url, decode_responses=True)
            self._client_ready = True
            return self._client
        except Exception as exc:  # noqa: BLE001 - checkpointing is best-effort
            self._degrade(f"cannot create Redis client: {exc}")
            return None

    def _degrade(self, reason: str) -> None:
        if self._healthy:
            log.warning("checkpoint persistence disabled (%s); using in-memory only", reason)
        self._healthy = False

    @staticmethod
    def _key(thread_id: str) -> str:
        return f"{KEY_PREFIX}:{thread_id}"

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as exc:  # noqa: BLE001
                log.debug("error closing redis client: %s", exc)
            finally:
                self._client = None
                self._client_ready = False

    # ── snapshot encode/decode ────────────────────────────────────────────

    def _snapshot(self, thread_id: str) -> str:
        storage = {
            ns: {
                checkpoint_id: [
                    _encode_blob(checkpoint),
                    _encode_blob(metadata),
                    parent_id,
                ]
                for checkpoint_id, (checkpoint, metadata, parent_id) in checkpoints.items()
            }
            for ns, checkpoints in self.storage.get(thread_id, {}).items()
        }
        blobs = [
            [ns, channel, version, _encode_blob(blob)]
            for (owner, ns, channel, version), blob in self.blobs.items()
            if owner == thread_id
        ]
        writes = [
            [ns, checkpoint_id, inner[0], inner[1], value[0], value[1], _encode_blob(value[2]), value[3]]
            for (owner, ns, checkpoint_id), inner_map in self.writes.items()
            if owner == thread_id
            for inner, value in inner_map.items()
        ]
        return json.dumps({"storage": storage, "blobs": blobs, "writes": writes})

    def _restore(self, thread_id: str, raw: str) -> None:
        payload = json.loads(raw)
        for ns, checkpoints in payload.get("storage", {}).items():
            for checkpoint_id, entry in checkpoints.items():
                self.storage[thread_id][ns][checkpoint_id] = (
                    _decode_blob(entry[0]),
                    _decode_blob(entry[1]),
                    entry[2],
                )
        for ns, channel, version, blob in payload.get("blobs", []):
            self.blobs[(thread_id, ns, channel, version)] = _decode_blob(blob)
        for ns, checkpoint_id, task_id, idx, w_task, channel, blob, path in payload.get("writes", []):
            self.writes[(thread_id, ns, checkpoint_id)][(task_id, idx)] = (
                w_task,
                channel,
                _decode_blob(blob),
                path,
            )

    async def _ensure_loaded(self, thread_id: str) -> None:
        if thread_id in self._loaded or not self._healthy:
            return
        async with self._lock:
            if thread_id in self._loaded:
                return
            self._loaded.add(thread_id)
            client = await self._redis()
            if client is None:
                return
            try:
                raw = await client.get(self._key(thread_id))
            except Exception as exc:  # noqa: BLE001
                self._degrade(f"read failed: {exc}")
                return
            if raw:
                try:
                    self._restore(thread_id, raw)
                    log.info("resumed checkpoint state for job %s from Redis", thread_id)
                except Exception as exc:  # noqa: BLE001 - corrupt snapshot must not block
                    log.warning("discarding unreadable checkpoint for %s: %s", thread_id, exc)

    async def _persist(self, thread_id: str) -> None:
        if not self._healthy:
            return
        client = await self._redis()
        if client is None:
            return
        try:
            await client.set(self._key(thread_id), self._snapshot(thread_id), ex=self._ttl)
        except Exception as exc:  # noqa: BLE001
            self._degrade(f"write failed: {exc}")

    # ── BaseCheckpointSaver async surface ─────────────────────────────────

    async def aget_tuple(self, config):
        await self._ensure_loaded(config["configurable"]["thread_id"])
        return self.get_tuple(config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        if config is not None:
            await self._ensure_loaded(config["configurable"]["thread_id"])
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions,
    ):
        thread_id = config["configurable"]["thread_id"]
        await self._ensure_loaded(thread_id)
        result = self.put(config, checkpoint, metadata, new_versions)
        await self._persist(thread_id)
        return result

    async def aput_writes(self, config, writes, task_id: str, task_path: str = "") -> None:
        thread_id = config["configurable"]["thread_id"]
        await self._ensure_loaded(thread_id)
        self.put_writes(config, writes, task_id, task_path)
        await self._persist(thread_id)

    async def adelete_thread(self, thread_id: str) -> None:
        self.delete_thread(thread_id)
        self._loaded.discard(thread_id)
        if not self._healthy:
            return
        client = await self._redis()
        if client is None:
            return
        try:
            await client.delete(self._key(thread_id))
        except Exception as exc:  # noqa: BLE001
            self._degrade(f"delete failed: {exc}")


def build_checkpointer(redis_url: str | None) -> InMemorySaver:
    """Redis-backed checkpointing when a URL is configured, in-memory otherwise."""

    if not redis_url:
        return InMemorySaver()
    return RedisCheckpointSaver(redis_url)
