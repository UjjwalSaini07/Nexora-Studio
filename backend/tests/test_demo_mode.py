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
            self.db = self.client["nexora_test_demo"]
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
async def test_production_mode_suppresses_duplicates(app_client):
    """
    In Production Mode (DEMO_MODE=False), running the same trigger a second time
    should return actions=[] because of suppression.
    """
    client, app = app_client
    
    # 1. Setup mock contexts
    category_payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
    merchant_payload = load_json(EXPANDED_DIR / "merchants" / "m_001_drmeera_dentist_delhi.json")
    trigger_payload = {
        "id": "trg_prod_test",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "payload": {"category": "dentists", "top_item_id": "d_2026W17_jida_fluoride"},
        "urgency": 2,
        "suppression_key": "sup_prod_test",
        "expires_at": "2026-12-31T23:59:59Z",
    }
    
    await client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": category_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    await client.post("/v1/context", json={"scope": "merchant", "context_id": "m_001_drmeera_dentist_delhi", "version": 1, "payload": merchant_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    await client.post("/v1/context", json={"scope": "trigger", "context_id": "trg_prod_test", "version": 1, "payload": trigger_payload, "delivered_at": "2026-04-26T09:00:00Z"})

    mock_response = {
        "body": "Prod test body now.",
        "cta": "open_ended",
        "send_as": "nexora",
        "template_params": [],
        "rationale": "Prod rationale.",
    }

    # Ensure DEMO_MODE is False
    with patch("composer.engine.DEMO_MODE", False), \
         patch("composer.output_validator.DEMO_MODE", False), \
         patch("routers.tick.DEMO_MODE", False):
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
            # First tick -> generates action
            resp1 = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:00:00Z",
                "available_triggers": ["trg_prod_test"]
            })
            actions1 = resp1.json()["actions"]
            assert len(actions1) == 1
            assert actions1[0]["trigger_id"] == "trg_prod_test"

            # Second tick -> should be suppressed (no actions returned)
            resp2 = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:05:00Z",
                "available_triggers": ["trg_prod_test"]
            })
            actions2 = resp2.json()["actions"]
            assert len(actions2) == 0


@pytest.mark.asyncio
async def test_demo_mode_allows_repeated_actions(app_client):
    """
    In Demo Mode (DEMO_MODE=True), running the same trigger repeatedly
    should always generate an action, ignoring wait states and suppression.
    """
    client, app = app_client
    
    category_payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
    merchant_payload = load_json(EXPANDED_DIR / "merchants" / "m_001_drmeera_dentist_delhi.json")
    trigger_payload = {
        "id": "trg_demo_test",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "payload": {"category": "dentists", "top_item_id": "d_2026W17_jida_fluoride"},
        "urgency": 2,
        "suppression_key": "sup_demo_test",
        "expires_at": "2026-12-31T23:59:59Z",
    }
    
    await client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": category_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    await client.post("/v1/context", json={"scope": "merchant", "context_id": "m_001_drmeera_dentist_delhi", "version": 1, "payload": merchant_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    await client.post("/v1/context", json={"scope": "trigger", "context_id": "trg_demo_test", "version": 1, "payload": trigger_payload, "delivered_at": "2026-04-26T09:00:00Z"})

    mock_response = {
        "body": "Demo test body now.",
        "cta": "open_ended",
        "send_as": "nexora",
        "template_params": [],
        "rationale": "Demo rationale.",
    }

    # Set wait state in redis
    conv_id = "conv_m_001_drmeera_dentist_delhi_research_digest"
    await app.state.redis.set_conversation_wait(conv_id, "2026-04-26T12:00:00Z")

    # Set suppression key in redis manually
    await app.state.redis.set_suppression("sup_demo_test")

    with patch("composer.engine.DEMO_MODE", True), \
         patch("composer.output_validator.DEMO_MODE", True), \
         patch("routers.tick.DEMO_MODE", True):
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
            # First tick -> generates action even though suppressed + wait state is active
            resp1 = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:00:00Z",
                "available_triggers": ["trg_demo_test"]
            })
            actions1 = resp1.json()["actions"]
            assert len(actions1) == 1
            assert actions1[0]["trigger_id"] == "trg_demo_test"

            # Second tick -> still generates action (ignores everything)
            resp2 = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:05:00Z",
                "available_triggers": ["trg_demo_test"]
            })
            actions2 = resp2.json()["actions"]
            assert len(actions2) == 1
            assert actions2[0]["trigger_id"] == "trg_demo_test"


@pytest.mark.asyncio
async def test_multi_trigger_processing_continues_on_skips(app_client):
    """
    If multiple triggers are provided, and one is skipped (e.g. expired or suppressed),
    the loop must continue evaluating and returned actions should include the valid ones.
    """
    client, app = app_client
    
    category_payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
    merchant_payload = load_json(EXPANDED_DIR / "merchants" / "m_001_drmeera_dentist_delhi.json")
    
    # Trigger A: valid
    trigger_a = {
        "id": "trg_multi_a",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "payload": {},
        "urgency": 2,
        "suppression_key": "sup_multi_a",
        "expires_at": "2026-12-31T23:59:59Z",
    }
    
    # Trigger B: expired (expires in 2025, but now is 2026)
    trigger_b = {
        "id": "trg_multi_b",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "payload": {},
        "urgency": 2,
        "suppression_key": "sup_multi_b",
        "expires_at": "2025-12-31T23:59:59Z",
    }

    await client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": category_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    await client.post("/v1/context", json={"scope": "merchant", "context_id": "m_001_drmeera_dentist_delhi", "version": 1, "payload": merchant_payload, "delivered_at": "2026-04-26T09:00:00Z"})
    for t in (trigger_a, trigger_b):
        await client.post("/v1/context", json={"scope": "trigger", "context_id": t["id"], "version": 1, "payload": t, "delivered_at": "2026-04-26T09:00:00Z"})

    mock_response = {
        "body": "Multi trigger body now.",
        "cta": "open_ended",
        "send_as": "nexora",
        "template_params": [],
        "rationale": "Multi rationale.",
    }

    # Production Mode (DEMO_MODE=False)
    with patch("composer.engine.DEMO_MODE", False), \
         patch("composer.output_validator.DEMO_MODE", False), \
         patch("routers.tick.DEMO_MODE", False):
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
            resp = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:00:00Z",
                "available_triggers": ["trg_multi_b", "trg_multi_a"]  # trg_multi_b is expired, trg_multi_a is valid
            })
            actions = resp.json()["actions"]
            # Trigger B (expired) was skipped, but Trigger A should still succeed!
            assert len(actions) == 1
            assert actions[0]["trigger_id"] == "trg_multi_a"
