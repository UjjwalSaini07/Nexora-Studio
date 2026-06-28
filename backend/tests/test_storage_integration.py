import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestRedisStoreContextVersioning:
    async def test_first_version_is_new(self, redis_store):
        is_new = await redis_store.set_context_version_if_new("merchant", "m_001", 1)
        assert is_new is True

    async def test_second_call_same_id_is_not_new(self, redis_store):
        await redis_store.set_context_version_if_new("merchant", "m_001", 1)
        is_new = await redis_store.set_context_version_if_new("merchant", "m_001", 2)
        assert is_new is False

    async def test_get_context_version_returns_minus_one_when_absent(self, redis_store):
        v = await redis_store.get_context_version("merchant", "m_unknown")
        assert v == -1

    async def test_context_count_increments_once_per_new_id(self, redis_store):
        await redis_store.set_context_version_if_new("merchant", "m_001", 1)
        await redis_store.set_context_version_if_new("merchant", "m_002", 1)
        await redis_store.set_context_version_if_new("merchant", "m_001", 2)  # not new
        counts = await redis_store.get_context_counts()
        assert counts["merchant"] == 2


class TestRedisStoreSuppression:
    async def test_not_suppressed_initially(self, redis_store):
        assert await redis_store.is_suppressed("sup_key_1") is False

    async def test_suppressed_after_set(self, redis_store):
        await redis_store.set_suppression("sup_key_1")
        assert await redis_store.is_suppressed("sup_key_1") is True


class TestRedisStoreConversation:
    async def test_append_and_get_turns(self, redis_store):
        await redis_store.append_turn("conv_1", {"from": "merchant", "message": "hi", "turn_number": 1})
        await redis_store.append_turn("conv_1", {"from": "nexora", "message": "hello", "turn_number": 2})
        turns = await redis_store.get_conversation("conv_1")
        assert len(turns) == 2
        assert turns[0]["message"] == "hi"

    async def test_conversation_not_ended_by_default(self, redis_store):
        assert await redis_store.is_conversation_ended("conv_x") is False

    async def test_mark_conversation_ended(self, redis_store):
        await redis_store.mark_conversation_ended("conv_x")
        assert await redis_store.is_conversation_ended("conv_x") is True

    async def test_auto_reply_count_increments(self, redis_store):
        c1 = await redis_store.increment_auto_reply("conv_y")
        c2 = await redis_store.increment_auto_reply("conv_y")
        assert c1 == 1
        assert c2 == 2

    async def test_auto_reply_count_resets(self, redis_store):
        await redis_store.increment_auto_reply("conv_z")
        await redis_store.reset_auto_reply_count("conv_z")
        assert await redis_store.get_auto_reply_count("conv_z") == 0

    async def test_sent_messages_tracked_for_anti_repetition(self, redis_store):
        await redis_store.append_sent_message("conv_1", "Hello there", "2026-06-25T10:00:00Z")
        sent = await redis_store.get_sent_messages("conv_1")
        assert len(sent) == 1
        assert sent[0]["body"] == "Hello there"


class TestMongoStoreContexts:
    async def test_upsert_and_get_context(self, mongo_store):
        await mongo_store.upsert_context("merchant", "m_001", 1, {"merchant_id": "m_001"}, "2026-06-25T10:00:00Z")
        doc = await mongo_store.get_context("merchant", "m_001")
        assert doc is not None
        assert doc["version"] == 1
        assert doc["payload"]["merchant_id"] == "m_001"

    async def test_upsert_replaces_existing(self, mongo_store):
        await mongo_store.upsert_context("merchant", "m_001", 1, {"v": 1}, "2026-06-25T10:00:00Z")
        await mongo_store.upsert_context("merchant", "m_001", 2, {"v": 2}, "2026-06-25T10:05:00Z")
        doc = await mongo_store.get_context("merchant", "m_001")
        assert doc["version"] == 2
        assert doc["payload"]["v"] == 2

    async def test_get_context_returns_none_when_absent(self, mongo_store):
        doc = await mongo_store.get_context("merchant", "m_missing")
        assert doc is None

    async def test_log_and_retrieve_actions(self, mongo_store):
        await mongo_store.log_action({"trigger_id": "trg_1", "body": "hi"})
        actions = await mongo_store.get_recent_actions(limit=10)
        assert len(actions) == 1
        assert actions[0]["trigger_id"] == "trg_1"
