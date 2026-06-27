# backend/tests/test_new_features.py
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
            self.db = self.client["nexora_test_features"]
            self.contexts = self.db["contexts"]
            self.conversations = self.db["conversations"]
            self.actions_log = self.db["actions_log"]
            self.replies_log = self.db["replies_log"]
            self.ticks_log = self.db["ticks_log"]
            self.suppressions_log = self.db["suppressions_log"]
            self.contexts_history = self.db["contexts_history"]

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


@pytest.mark.asyncio
async def test_demo_reset_clears_demo_state_only(app_client):
    """
    POST /v1/demo/reset should clear suppression keys, wait states, and conversations in Redis,
    and suppressions log in MongoDB. It must NOT delete category, merchant, customer, or trigger contexts.
    """
    client, app = app_client

    # 1. Seed some category, merchant, and trigger contexts
    category_payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
    merchant_payload = load_json(EXPANDED_DIR / "merchants" / "m_001_drmeera_dentist_delhi.json")
    
    await client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": category_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    await client.post("/v1/context", json={"scope": "merchant", "context_id": "m_001_drmeera_dentist_delhi", "version": 1, "payload": merchant_payload, "delivered_at": "2026-04-26T09:00:00Z"})

    # 2. Add some demo-specific wait states, suppression keys, and conversation turns to Redis/Mongo
    await app.state.redis.set_conversation_wait("conv_test", "2026-04-26T12:00:00Z")
    await app.state.redis.set_suppression("sup_test")
    await app.state.mongo.log_suppression("sup_test")
    await app.state.redis.append_sent_message("conv_test", "Hello", "2026-04-26T10:00:00Z")

    # 3. Call reset endpoint
    reset_resp = await client.post("/v1/demo/reset")
    assert reset_resp.status_code == 200
    data = reset_resp.json()
    assert data["success"] is True
    assert data["suppression_keys_removed"] >= 1
    assert data["wait_states_removed"] == 1
    assert data["conversation_states_removed"] >= 1

    # 4. Verify context data was NOT deleted
    health_resp = await client.get("/v1/healthz")
    counts = health_resp.json()["contexts_loaded"]
    assert counts["category"] == 1
    assert counts["merchant"] == 1

    # 5. Verify demo state is cleared in Redis
    assert await app.state.redis.get_conversation_wait("conv_test") is None
    assert await app.state.redis.is_suppressed("sup_test") is False
    assert await app.state.redis.get_sent_messages("conv_test") == []


@pytest.mark.asyncio
async def test_processing_time_metrics_present(app_client):
    """
    Verify that processing_ms is present in the response of /v1/context, /v1/tick, and /v1/reply.
    """
    client, app = app_client

    # /v1/context metric
    category_payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
    resp_ctx = await client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": category_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    assert resp_ctx.status_code == 200
    assert "processing_ms" in resp_ctx.json()
    assert resp_ctx.json()["processing_ms"] >= 0.0

    # Load merchant and trigger for /v1/tick
    merchant_payload = load_json(EXPANDED_DIR / "merchants" / "m_001_drmeera_dentist_delhi.json")
    trigger_payload = {
        "id": "trg_metrics_test",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "payload": {"category": "dentists", "top_item_id": "d_2026W17_jida_fluoride"},
        "urgency": 2,
        "suppression_key": "sup_metrics_test",
        "expires_at": "2026-12-31T23:59:59Z",
    }
    await client.post("/v1/context", json={"scope": "merchant", "context_id": "m_001_drmeera_dentist_delhi", "version": 1, "payload": merchant_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    await client.post("/v1/context", json={"scope": "trigger", "context_id": "trg_metrics_test", "version": 1, "payload": trigger_payload, "delivered_at": "2026-04-26T09:00:00Z"})

    mock_response = {
        "body": "Prod test body now.",
        "cta": "open_ended",
        "send_as": "nexora",
        "template_params": [],
        "rationale": "Prod rationale.",
    }

    # /v1/tick metric
    with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
        resp_tick = await client.post("/v1/tick", json={
            "now": "2026-04-26T10:00:00Z",
            "available_triggers": ["trg_metrics_test"]
        })
        assert resp_tick.status_code == 200
        assert "processing_ms" in resp_tick.json()
        assert resp_tick.json()["processing_ms"] >= 0.0

        # Verify rich action metadata
        action = resp_tick.json()["actions"][0]
        assert "priority_score" in action
        assert "priority_rank" in action
        assert action["trigger_kind"] == "research_digest"
        assert action["urgency"] == 2
        assert action["expires_at"] == "2026-12-31T23:59:59Z"

    # /v1/reply metric
    reply_payload = {
        "conversation_id": "conv_metrics_test",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "from_role": "merchant",
        "message": "Send the list now.",
        "received_at": "2026-04-26T10:05:00Z",
        "turn_number": 2,
    }
    # Pre-populate history to allow standard reply flow
    await app.state.redis.append_sent_message("conv_metrics_test", "Hello", "2026-04-26T10:00:00Z")
    
    with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
        resp_reply = await client.post("/v1/reply", json=reply_payload)
        assert resp_reply.status_code == 200
        assert "processing_ms" in resp_reply.json()
        assert resp_reply.json()["processing_ms"] >= 0.0


@pytest.mark.asyncio
async def test_explainability_endpoint(app_client):
    """
    Verify GET /v1/action/{conversation_id}/explain returns the correct action analysis.
    """
    client, app = app_client

    # 1. Push some fake logs into MongoDB actions_log
    logged_action = {
        "conversation_id": "conv_explain_test",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "send_as": "nexora",
        "trigger_id": "trg_explain_test",
        "template_name": "nexora_research_digest_v1",
        "template_params": ["Meera", "Prod test body now.", "open_ended"],
        "body": "Prod test body now.",
        "cta": "open_ended",
        "suppression_key": "sup_explain_test",
        "rationale": "Test rationale.",
        "merchant": "Dr. Meera's Clinic",
        "trigger": "research_digest",
        "category": "dentists",
        "confidence": 0.95,
        "priority_score": 45,
        "priority_rank": 1,
        "priority_reason": "urgency=3/5, etc.",
        "logged_at": "2026-04-26T10:01:00Z"
    }
    await app.state.mongo.actions_log.insert_one(logged_action)

    # 2. Seed required contexts
    category_payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
    merchant_payload = load_json(EXPANDED_DIR / "merchants" / "m_001_drmeera_dentist_delhi.json")
    await client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": category_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    await client.post("/v1/context", json={"scope": "merchant", "context_id": "m_001_drmeera_dentist_delhi", "version": 1, "payload": merchant_payload, "delivered_at": "2026-04-26T09:00:00Z"})

    # 3. Call explain endpoint
    explain_resp = await client.get("/v1/action/conv_explain_test/explain")
    assert explain_resp.status_code == 200
    data = explain_resp.json()
    assert data["conversation_id"] == "conv_explain_test"
    assert data["trigger_id"] == "trg_explain_test"
    assert data["confidence_score"] == 0.95
    assert len(data["merchant_signals_used"]) > 0
    assert "urgency" in data["why_selected"]
    assert "priority_breakdown" in data
    assert "suppression_status" in data
    assert "wait_state_status" in data
    
    # 4. Verify 404 for unknown conversation ID
    unknown_resp = await client.get("/v1/action/conv_unknown/explain")
    assert unknown_resp.status_code == 404
