import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

import fakeredis.aioredis
import mongomock_motor

from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore


class FakeRedisStore(RedisStore):
    """Same interface as RedisStore, backed by fakeredis instead of a real server."""
    def __init__(self):
        self.r = fakeredis.aioredis.FakeRedis(decode_responses=True)


class FakeMongoStore(MongoStore):
    """Same interface as MongoStore, backed by mongomock-motor instead of a real server."""
    def __init__(self):
        self.client = mongomock_motor.AsyncMongoMockClient()
        self.db = self.client["nexora_bot_test"]
        self.contexts = self.db["contexts"]
        self.conversations = self.db["conversations"]
        self.actions_log = self.db["actions_log"]
        self.replies_log = self.db["replies_log"]
        self.ticks_log = self.db["ticks_log"]
        self.suppressions_log = self.db["suppressions_log"]
        self.contexts_history = self.db["contexts_history"]

    async def ping(self) -> bool:
        return True

    async def ensure_indexes(self):
        # mongomock supports create_index, but indexes aren't load-bearing
        # for correctness in tests, so this is a no-op for speed/simplicity.
        return None


@pytest_asyncio.fixture
async def redis_store():
    store = FakeRedisStore()
    yield store
    await store.r.flushall()


@pytest_asyncio.fixture
async def mongo_store():
    store = FakeMongoStore()
    yield store
