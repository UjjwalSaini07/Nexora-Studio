# backend/tests/test_api_integration.py
"""
End-to-end integration tests against the real FastAPI app, using:
- fakeredis / mongomock-motor in place of real Redis/Mongo (via dependency
  overrides on app.state, set up in the `client` fixture below)
- the REAL official challenge dataset (expanded/) as fixture data
- a mocked LLMClient.complete() so the test suite is fully offline and
  deterministic (no live Groq key required to validate correctness of the
  HTTP contract, idempotency, suppression, and reply state machine)

This exercises exactly the request/response shapes documented in
challenge-testing-brief.md and examples/api-call-examples.md.
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
    """Builds the real FastAPI app with fake stores, no dataset autoload
    (so each test controls exactly what's pushed), and yields an AsyncClient."""
    import main as main_module
    from storage.redis_store import RedisStore
    from storage.mongo_store import MongoStore

    class FakeRedisStore(RedisStore):
        def __init__(self):
            self.r = fakeredis.aioredis.FakeRedis(decode_responses=True)

    class FakeMongoStore(MongoStore):
        def __init__(self):
            self.client = mongomock_motor.AsyncMongoMockClient()
            self.db = self.client["nexora_test"]
            self.contexts = self.db["contexts"]
            self.conversations = self.db["conversations"]
            self.actions_log = self.db["actions_log"]
            self.replies_log = self.db["replies_log"]
            self.ticks_log = self.db["ticks_log"]
            self.suppressions_log = self.db["suppressions_log"]

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


class TestHealthzAndMetadata:
    async def test_healthz_returns_ok_with_zero_counts_initially(self, app_client):
        client, app = app_client
        resp = await client.get("/v1/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["contexts_loaded"] == {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}

    async def test_metadata_has_required_fields(self, app_client):
        client, app = app_client
        resp = await client.get("/v1/metadata")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["team_name", "team_members", "model", "approach", "contact_email", "version", "submitted_at"]:
            assert field in data


class TestContextEndpoint:
    async def test_push_category_context_accepted(self, app_client):
        client, app = app_client
        payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
        resp = await client.post("/v1/context", json={
            "scope": "category", "context_id": "dentists", "version": 1,
            "payload": payload, "delivered_at": "2026-06-25T09:45:00Z",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] is True
        assert "ack_id" in data

    async def test_idempotent_same_version_rejected(self, app_client):
        client, app = app_client
        payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
        body = {
            "scope": "category", "context_id": "dentists", "version": 1,
            "payload": payload, "delivered_at": "2026-06-25T09:45:00Z",
        }
        await client.post("/v1/context", json=body)
        resp = await client.post("/v1/context", json=body)
        data = resp.json()
        assert data["accepted"] is False
        assert data["reason"] == "stale_version"
        assert data["current_version"] == 1

    async def test_version_bump_accepted_and_replaces(self, app_client):
        client, app = app_client
        payload = load_json(EXPANDED_DIR / "categories" / "dentists.json")
        await client.post("/v1/context", json={
            "scope": "category", "context_id": "dentists", "version": 1,
            "payload": payload, "delivered_at": "2026-06-25T09:45:00Z",
        })
        payload2 = dict(payload)
        payload2["digest"] = payload["digest"] + [{
            "id": "d_NEW", "kind": "news", "title": "New item", "source": "Test"
        }]
        resp = await client.post("/v1/context", json={
            "scope": "category", "context_id": "dentists", "version": 2,
            "payload": payload2, "delivered_at": "2026-06-25T10:00:00Z",
        })
        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

        doc = await app.state.mongo.get_context("category", "dentists")
        assert doc["version"] == 2
        assert len(doc["payload"]["digest"]) == len(payload["digest"]) + 1

    async def test_invalid_scope_rejected(self, app_client):
        client, app = app_client
        resp = await client.post("/v1/context", json={
            "scope": "not_a_real_scope", "context_id": "x", "version": 1,
            "payload": {}, "delivered_at": "2026-06-25T09:45:00Z",
        })
        assert resp.status_code == 400

    async def test_healthz_reflects_loaded_contexts(self, app_client):
        client, app = app_client
        for slug in ["dentists", "salons", "restaurants", "gyms", "pharmacies"]:
            payload = load_json(EXPANDED_DIR / "categories" / f"{slug}.json")
            await client.post("/v1/context", json={
                "scope": "category", "context_id": slug, "version": 1,
                "payload": payload, "delivered_at": "2026-06-25T09:45:00Z",
            })
        resp = await client.get("/v1/healthz")
        assert resp.json()["contexts_loaded"]["category"] == 5

    async def test_push_real_merchant_and_customer(self, app_client):
        client, app = app_client
        merchant_files = sorted((EXPANDED_DIR / "merchants").glob("*.json"))[:3]
        for f in merchant_files:
            payload = load_json(f)
            resp = await client.post("/v1/context", json={
                "scope": "merchant", "context_id": payload["merchant_id"], "version": 1,
                "payload": payload, "delivered_at": "2026-06-25T09:45:00Z",
            })
            assert resp.status_code == 200
            assert resp.json()["accepted"] is True


class TestTickEndpoint:
    async def _push_full_context_for_trigger(self, client, trigger_payload):
        """Helper: push category + merchant + (customer if needed) + the trigger itself."""
        merchant_id = trigger_payload["merchant_id"]
        merchant_path = EXPANDED_DIR / "merchants" / f"{merchant_id}.json"
        merchant_payload = load_json(merchant_path)

        category_slug = merchant_payload["category_slug"]
        category_payload = load_json(EXPANDED_DIR / "categories" / f"{category_slug}.json")

        await client.post("/v1/context", json={
            "scope": "category", "context_id": category_slug, "version": 1,
            "payload": category_payload, "delivered_at": "2026-06-25T09:45:00Z",
        })
        await client.post("/v1/context", json={
            "scope": "merchant", "context_id": merchant_id, "version": 1,
            "payload": merchant_payload, "delivered_at": "2026-06-25T09:45:00Z",
        })

        if trigger_payload.get("customer_id"):
            customer_path = EXPANDED_DIR / "customers" / f"{trigger_payload['customer_id']}.json"
            if customer_path.exists():
                customer_payload = load_json(customer_path)
                await client.post("/v1/context", json={
                    "scope": "customer", "context_id": trigger_payload["customer_id"], "version": 1,
                    "payload": customer_payload, "delivered_at": "2026-06-25T09:45:00Z",
                })

        await client.post("/v1/context", json={
            "scope": "trigger", "context_id": trigger_payload["id"], "version": 1,
            "payload": trigger_payload, "delivered_at": "2026-06-25T09:45:00Z",
        })

    async def test_tick_with_no_triggers_returns_empty_actions(self, app_client):
        client, app = app_client
        resp = await client.post("/v1/tick", json={"now": "2026-06-25T10:35:00Z", "available_triggers": []})
        assert resp.status_code == 200
        assert resp.json() == {"actions": []}

    async def test_tick_composes_action_for_real_trigger(self, app_client):
        client, app = app_client
        trigger_path = EXPANDED_DIR / "triggers" / "trg_001_research_digest_dentists.json"
        trigger_payload = load_json(trigger_path)
        await self._push_full_context_for_trigger(client, trigger_payload)

        mock_llm_response = {
            "body": "Dr. Meera, JIDA's Oct issue landed. Worth a look. Want the abstract?",
            "cta": "open_ended",
            "send_as": "nexora",
            "template_params": ["Meera", "JIDA", "open_ended"],
            "rationale": "Research digest anchored on high-risk-adult-relevant trial.",
        }
        # NOTE: the seed dataset's trigger `expires_at` values are authored
        # relative to the challenge's own timeline (late April 2026), not
        # whatever the real wall-clock date happens to be when tests run.
        # Use an in-timeline "now" so we're testing composition logic, not
        # accidentally testing the expiry-skip path.
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_llm_response)):
            resp = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:35:00Z",
                "available_triggers": [trigger_payload["id"]],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["actions"]) == 1
        action = data["actions"][0]
        for field in ["conversation_id", "merchant_id", "send_as", "trigger_id",
                      "template_name", "template_params", "body", "cta",
                      "suppression_key", "rationale"]:
            assert field in action
        assert action["trigger_id"] == trigger_payload["id"]
        assert action["send_as"] == "nexora"
        assert "http" not in action["body"]

    async def test_tick_suppresses_already_sent_trigger(self, app_client):
        client, app = app_client
        trigger_path = EXPANDED_DIR / "triggers" / "trg_001_research_digest_dentists.json"
        trigger_payload = load_json(trigger_path)
        await self._push_full_context_for_trigger(client, trigger_payload)

        mock_llm_response = {
            "body": "First message about the digest item.",
            "cta": "open_ended", "send_as": "nexora",
            "template_params": [], "rationale": "x",
        }
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_llm_response)):
            resp1 = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:35:00Z", "available_triggers": [trigger_payload["id"]],
            })
            assert len(resp1.json()["actions"]) == 1

            # Same trigger again -> should be suppressed (already sent)
            resp2 = await client.post("/v1/tick", json={
                "now": "2026-04-26T10:40:00Z", "available_triggers": [trigger_payload["id"]],
            })
            assert resp2.json()["actions"] == []

    async def test_tick_handles_customer_scoped_trigger(self, app_client):
        client, app = app_client
        # Find a real customer-scoped trigger from the dataset
        trigger_files = sorted((EXPANDED_DIR / "triggers").glob("*.json"))
        customer_trigger = None
        for f in trigger_files:
            t = load_json(f)
            if t.get("scope") == "customer" and t.get("customer_id"):
                customer_path = EXPANDED_DIR / "customers" / f"{t['customer_id']}.json"
                if customer_path.exists():
                    customer_trigger = t
                    break
        assert customer_trigger is not None, "Expected at least one customer-scoped trigger with a resolvable customer in the dataset"

        await self._push_full_context_for_trigger(client, customer_trigger)

        mock_llm_response = {
            "body": "Hi! Your recall is due. Reply 1 for Wed or 2 for Thu.",
            "cta": "multi_choice_slot", "send_as": "nexora",  # intentionally wrong, validator should fix
            "template_params": [], "rationale": "x",
        }
        # Derive a "now" that is safely before this specific trigger's
        # expires_at, regardless of which record the dataset generator
        # happened to produce first (seed dataset triggers span a wide
        # range of authored expiry dates).
        from datetime import datetime, timedelta
        expires = datetime.fromisoformat(customer_trigger["expires_at"].replace("Z", "+00:00"))
        now_iso = (expires - timedelta(days=1)).isoformat().replace("+00:00", "Z")

        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_llm_response)):
            resp = await client.post("/v1/tick", json={
                "now": now_iso,
                "available_triggers": [customer_trigger["id"]],
            })

        assert resp.status_code == 200
        actions = resp.json()["actions"]
        assert len(actions) == 1
        assert actions[0]["send_as"] == "merchant_on_behalf"  # auto-corrected by validator
        assert actions[0]["customer_id"] == customer_trigger["customer_id"]


class TestReplyEndpoint:
    async def test_auto_reply_then_wait_then_end(self, app_client):
        client, app = app_client
        auto_msg = "Thank you for contacting us! Our team will respond shortly."

        resp1 = await client.post("/v1/reply", json={
            "conversation_id": "conv_auto_1", "merchant_id": "m_test",
            "from_role": "merchant", "message": auto_msg,
            "received_at": "2026-06-25T10:00:00Z", "turn_number": 2,
        })
        assert resp1.json()["action"] == "send"

        resp2 = await client.post("/v1/reply", json={
            "conversation_id": "conv_auto_1", "merchant_id": "m_test",
            "from_role": "merchant", "message": auto_msg,
            "received_at": "2026-06-25T10:05:00Z", "turn_number": 3,
        })
        assert resp2.json()["action"] == "wait"

        resp3 = await client.post("/v1/reply", json={
            "conversation_id": "conv_auto_1", "merchant_id": "m_test",
            "from_role": "merchant", "message": auto_msg,
            "received_at": "2026-06-25T10:10:00Z", "turn_number": 4,
        })
        assert resp3.json()["action"] == "end"

    async def test_hostile_message_handled_gracefully(self, app_client):
        client, app = app_client
        resp = await client.post("/v1/reply", json={
            "conversation_id": "conv_hostile_1", "merchant_id": "m_test",
            "from_role": "merchant", "message": "Stop messaging me. This is useless spam.",
            "received_at": "2026-06-25T10:00:00Z", "turn_number": 2,
        })
        data = resp.json()
        assert data["action"] == "send"
        assert "apolog" in data["body"].lower() or "won't" in data["body"].lower()

    async def test_intent_transition_calls_llm(self, app_client):
        client, app = app_client
        mock_llm_response = {
            "action": "send",
            "body": "Great, drafting it now. Reply CONFIRM to send.",
            "cta": "binary_confirm_cancel",
            "rationale": "Merchant committed; switching to action mode.",
        }
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_llm_response)):
            resp = await client.post("/v1/reply", json={
                "conversation_id": "conv_intent_1", "merchant_id": "m_test",
                "from_role": "merchant", "message": "Ok lets do it. Whats next?",
                "received_at": "2026-06-25T10:00:00Z", "turn_number": 2,
            })
        data = resp.json()
        assert data["action"] == "send"
        assert "rationale" in data

    async def test_ended_conversation_stays_ended(self, app_client):
        client, app = app_client
        await app.state.redis.mark_conversation_ended("conv_done")
        resp = await client.post("/v1/reply", json={
            "conversation_id": "conv_done", "merchant_id": "m_test",
            "from_role": "merchant", "message": "hello again",
            "received_at": "2026-06-25T10:00:00Z", "turn_number": 5,
        })
        assert resp.json()["action"] == "end"
