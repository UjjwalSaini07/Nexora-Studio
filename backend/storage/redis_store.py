# backend/storage/redis_store.py
"""
RedisStore: versioned context index, suppression (dedup) keys, conversation
state, and auto-reply streak tracking.

All writes that must be atomic (context version bump + first-seen count) use
a Redis transaction (MULTI/EXEC via pipeline) to avoid race conditions if the
judge harness fires concurrent /v1/context calls for the same context_id.
"""
import json
import time
from typing import Optional

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from config import REDIS_URL
from logging_config import get_logger

logger = get_logger("nexora.redis_store")


class RedisStore:
    def __init__(self, url: str = REDIS_URL):
        self.r = aioredis.from_url(url, decode_responses=True)

    async def ping(self) -> bool:
        try:
            return await self.r.ping()
        except RedisError as exc:
            logger.error("Redis ping failed", extra={"ctx": {"error": str(exc)}})
            return False

    async def close(self):
        await self.r.close()

    # ── Context version index ───────────────────────────────────
    async def get_context_version(self, scope: str, context_id: str) -> int:
        key = f"nexora:ctx_version:{scope}:{context_id}"
        v = await self.r.get(key)
        return int(v) if v is not None else -1

    async def set_context_version(self, scope: str, context_id: str, version: int):
        key = f"nexora:ctx_version:{scope}:{context_id}"
        await self.r.set(key, str(version))

    async def set_context_version_if_new(self, scope: str, context_id: str, version: int) -> bool:
        """
        Atomically: if no version is stored yet, set it and bump the
        scope counter. Returns True if this was the FIRST time this
        context_id was ever stored (used to decide whether to increment
        contexts_loaded counts exactly once).
        """
        version_key = f"nexora:ctx_version:{scope}:{context_id}"
        count_key = f"nexora:ctx_count:{scope}"

        async with self.r.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(version_key)
                    current = await pipe.get(version_key)
                    pipe.multi()
                    if current is None:
                        pipe.set(version_key, str(version))
                        pipe.incr(count_key)
                        await pipe.execute()
                        return True
                    else:
                        pipe.set(version_key, str(version))
                        await pipe.execute()
                        return False
                except aioredis.WatchError:
                    continue

    # ── Context count (for /healthz) ────────────────────────────
    async def increment_context_count(self, scope: str):
        await self.r.incr(f"nexora:ctx_count:{scope}")

    async def get_context_counts(self) -> dict:
        scopes = ["category", "merchant", "customer", "trigger"]
        counts = {}
        for s in scopes:
            v = await self.r.get(f"nexora:ctx_count:{s}")
            counts[s] = int(v) if v else 0
        return counts

    # ── Suppression (dedup) ─────────────────────────────────────
    async def is_suppressed(self, suppression_key: str) -> bool:
        return (await self.r.exists(f"nexora:suppress:{suppression_key}")) > 0

    async def set_suppression(self, suppression_key: str, ttl_seconds: int = 86400 * 7):
        await self.r.setex(f"nexora:suppress:{suppression_key}", ttl_seconds, "1")

    # ── Conversation state ───────────────────────────────────────
    async def get_conversation(self, conv_id: str) -> list:
        raw = await self.r.get(f"nexora:conv:{conv_id}")
        return json.loads(raw) if raw else []

    async def append_turn(self, conv_id: str, turn: dict):
        turns = await self.get_conversation(conv_id)
        turns.append(turn)
        await self.r.setex(f"nexora:conv:{conv_id}", 86400 * 30, json.dumps(turns))

    async def append_sent_message(self, conv_id: str, body: str, sent_at: str):
        """Record what NEXORA itself sent, for anti-repetition checks."""
        key = f"nexora:conv_sent:{conv_id}"
        raw = await self.r.get(key)
        sent = json.loads(raw) if raw else []
        sent.append({"body": body, "sent_at": sent_at})
        await self.r.setex(key, 86400 * 30, json.dumps(sent))

    async def get_sent_messages(self, conv_id: str) -> list:
        raw = await self.r.get(f"nexora:conv_sent:{conv_id}")
        return json.loads(raw) if raw else []

    async def mark_conversation_ended(self, conv_id: str):
        await self.r.setex(f"nexora:conv_ended:{conv_id}", 86400 * 30, "1")

    async def is_conversation_ended(self, conv_id: str) -> bool:
        return (await self.r.exists(f"nexora:conv_ended:{conv_id}")) > 0

    # ── Auto-reply tracking ─────────────────────────────────────
    async def get_auto_reply_count(self, conv_id: str) -> int:
        v = await self.r.get(f"nexora:auto_reply_count:{conv_id}")
        return int(v) if v else 0

    async def increment_auto_reply(self, conv_id: str) -> int:
        key = f"nexora:auto_reply_count:{conv_id}"
        count = await self.r.incr(key)
        await self.r.expire(key, 86400)
        return count

    async def reset_auto_reply_count(self, conv_id: str):
        await self.r.delete(f"nexora:auto_reply_count:{conv_id}")

    # ── Rate limiting (sliding-window counter, used by middleware) ──
    async def rate_limit_hit(self, bucket_key: str, window_seconds: int, limit: int) -> tuple[bool, int]:
        """Returns (allowed, current_count) for a fixed-window counter."""
        key = f"nexora:ratelimit:{bucket_key}:{int(time.time()) // window_seconds}"
        count = await self.r.incr(key)
        if count == 1:
            await self.r.expire(key, window_seconds)
        return count <= limit, count

    # ── Uptime ──────────────────────────────────────────────────
    async def get_start_time(self) -> float:
        v = await self.r.get("nexora:start_time")
        if not v:
            t = str(time.time())
            await self.r.set("nexora:start_time", t)
            return float(t)
        return float(v)

    # ── Teardown (privacy requirement: wipe all state on request) ──
    async def wipe_all_nexora_keys(self) -> int:
        """
        Deletes every key under the `nexora:*` namespace. Used by the
        optional POST /v1/teardown endpoint per challenge-testing-brief.md
        §11: bots must not persist context data after the test ends.
        Uses SCAN (not KEYS) to avoid blocking Redis on large keyspaces.
        """
        deleted = 0
        cursor = 0
        while True:
            cursor, keys = await self.r.scan(cursor=cursor, match="nexora:*", count=500)
            if keys:
                deleted += await self.r.delete(*keys)
            if cursor == 0:
                break
        return deleted
