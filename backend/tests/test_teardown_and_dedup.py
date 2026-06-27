# backend/tests/test_teardown_and_dedup.py
"""
Tests for two contract requirements from challenge-testing-brief.md:

1. §11 (privacy): bots must not persist context data after the test ends.
   POST /v1/teardown wipes all state.
2. FAQ: only one action per (merchant_id, conversation_id) pair per tick.
"""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))

import fakeredis.aioredis
import mongomock_motor

EXPANDED_DIR = Path(__file__).parent.parent.parent / "expanded"


@pytest_asyncio.fixture
async def app_client():
    import main as main_module
    from storage.redis_store import RedisStore
    from storage.mongo_store import MongoStore

    class FakeRedisStore(RedisStore):
        def __init__(self):
            self.r = fakeredis.aioredis.FakeRedis(decode_responses=True)

    class FakeMongoStore(MongoStore):
        def __init__(self):
            self.client = mongomock_motor.AsyncMongoMockClient()
            self.db = self.client["nexora_test_teardown"]
            self.contexts = self.db["contexts"]
            self.conversations = self.db["conversations"]
            self.actions_log = self.db["actions_log"]
            self.replies_log = self.db["replies_log"]

        async def ping(self):
            return True

        async def ensure_indexes(self):
            return None

    app = main_module.app
    app.state.redis = FakeRedisStore()
    app.state.mongo = FakeMongoStore()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, app

    await app.state.redis.close()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class TestTeardown:
    async def test_teardown_wipes_pushed_contexts(self, app_client):
        client, app = app_client
        payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
        await client.post("/v1/context", json={
            "scope": "category", "context_id": "dentists", "version": 1,
            "payload": payload, "delivered_at": "2026-04-26T09:45:00Z",
        })
        resp = await client.get("/v1/healthz")
        assert resp.json()["contexts_loaded"]["category"] == 1

        teardown_resp = await client.post("/v1/teardown")
        assert teardown_resp.status_code == 200
        data = teardown_resp.json()
        assert data["status"] == "wiped"

        resp2 = await client.get("/v1/healthz")
        assert resp2.json()["contexts_loaded"] == {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}

    async def test_teardown_is_idempotent(self, app_client):
        client, app = app_client
        resp1 = await client.post("/v1/teardown")
        resp2 = await client.post("/v1/teardown")
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    async def test_teardown_clears_conversation_state(self, app_client):
        client, app = app_client
        await client.post("/v1/reply", json={
            "conversation_id": "conv_teardown_test", "merchant_id": "m_test",
            "from_role": "merchant", "message": "hello",
            "received_at": "2026-06-25T10:00:00Z", "turn_number": 2,
        })
        turns_before = await app.state.redis.get_conversation("conv_teardown_test")
        assert len(turns_before) == 1

        await client.post("/v1/teardown")

        turns_after = await app.state.redis.get_conversation("conv_teardown_test")
        assert turns_after == []


class TestTickDedup:
    async def test_only_one_action_per_merchant_conversation_pair(self, app_client):
        """
        Construct two distinct triggers that deliberately resolve to the
        SAME conversation_id (same merchant_id + same trigger.kind) and
        confirm only one action is returned for that tick.
        """
        client, app = app_client
        merchant_payload = load_json(EXPANDED_DIR / "merchants" / "m_001_drmeera_dentist_delhi.json")
        category_payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")

        await client.post("/v1/context", json={
            "scope": "category", "context_id": "dentists", "version": 1,
            "payload": category_payload, "delivered_at": "2026-04-26T09:45:00Z",
        })
        await client.post("/v1/context", json={
            "scope": "merchant", "context_id": merchant_payload["merchant_id"], "version": 1,
            "payload": merchant_payload, "delivered_at": "2026-04-26T09:46:00Z",
        })

        # Two distinct trigger IDs, same kind + merchant -> same conversation_id
        trigger_a = {
            "id": "trg_dedup_a", "scope": "merchant", "kind": "research_digest",
            "source": "external", "merchant_id": merchant_payload["merchant_id"],
            "payload": {}, "suppression_key": "sup_dedup_a", "expires_at": "2026-12-31T23:59:59Z",
        }
        trigger_b = {
            "id": "trg_dedup_b", "scope": "merchant", "kind": "research_digest",
            "source": "external", "merchant_id": merchant_payload["merchant_id"],
            "payload": {}, "suppression_key": "sup_dedup_b", "expires_at": "2026-12-31T23:59:59Z",
        }
        for t in (trigger_a, trigger_b):
            await client.post("/v1/context", json={
                "scope": "trigger", "context_id": t["id"], "version": 1,
                "payload": t, "delivered_at": "2026-04-26T09:47:00Z",
            })

        mock_response = {
            "body": "Distinct mock body for dedup test.",
            "cta": "open_ended", "send_as": "nexora",
            "template_params": [], "rationale": "x",
        }
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
            resp = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:00:00Z",
                "available_triggers": ["trg_dedup_a", "trg_dedup_b"],
            })

        actions = resp.json()["actions"]
        # Both triggers resolve to conv_{merchant_id}_research_digest (same
        # pair) -> only one action should survive the per-tick dedup guard.
        assert len(actions) == 1
