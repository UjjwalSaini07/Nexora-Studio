# backend/tests/test_warmup_and_test_pairs.py
"""
Validates two specific contractual requirements from the official briefs:

1. challenge-testing-brief.md §4 Phase 1: after the judge pushes the full
   base dataset (5 categories + 50 merchants + 200 customers, 0 triggers),
   GET /v1/healthz must report contexts_loaded reflecting all 255 base
   contexts.

2. The official generate_dataset.py produces expanded/test_pairs.json — 30
   canonical (merchant, trigger[, customer]) pairs every candidate is
   scored against. This test proves every pair resolves to a valid,
   loadable (category, merchant, trigger[, customer]) tuple and that the
   bot can produce a tick action for each one (with the LLM call mocked).
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
            self.db = self.client["nexora_test_warmup"]
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
    return json.loads(path.read_text())


class TestWarmupPhase:
    """Mirrors challenge-testing-brief.md §4 Phase 1 exactly."""

    async def test_full_base_dataset_warmup_shows_255_contexts(self, app_client):
        client, app = app_client

        # healthz before warmup: all zero
        resp = await client.get("/v1/healthz")
        assert resp.json()["contexts_loaded"] == {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}

        # Push 5 category contexts
        for f in sorted((EXPANDED_DIR / "categories").glob("*.json")):
            payload = load_json(f)
            resp = await client.post("/v1/context", json={
                "scope": "category", "context_id": payload["slug"], "version": 1,
                "payload": payload, "delivered_at": "2026-04-26T09:45:00Z",
            })
            assert resp.json()["accepted"] is True

        # Push 50 merchant contexts
        for f in sorted((EXPANDED_DIR / "merchants").glob("*.json")):
            payload = load_json(f)
            resp = await client.post("/v1/context", json={
                "scope": "merchant", "context_id": payload["merchant_id"], "version": 1,
                "payload": payload, "delivered_at": "2026-04-26T09:46:00Z",
            })
            assert resp.json()["accepted"] is True

        # Push 200 customer contexts
        for f in sorted((EXPANDED_DIR / "customers").glob("*.json")):
            payload = load_json(f)
            resp = await client.post("/v1/context", json={
                "scope": "customer", "context_id": payload["customer_id"], "version": 1,
                "payload": payload, "delivered_at": "2026-04-26T09:47:00Z",
            })
            assert resp.json()["accepted"] is True

        # No triggers pushed yet — per the brief, triggers arrive during the
        # test window, not at warmup.
        resp = await client.get("/v1/healthz")
        counts = resp.json()["contexts_loaded"]
        assert counts["category"] == 5
        assert counts["merchant"] == 50
        assert counts["customer"] == 200
        assert counts["trigger"] == 0
        assert counts["category"] + counts["merchant"] + counts["customer"] == 255


class TestCanonicalTestPairs:
    """Validates expanded/test_pairs.json — the 30 canonical scoring pairs."""

    def test_test_pairs_file_has_30_pairs(self):
        pairs = load_json(EXPANDED_DIR / "test_pairs.json")["pairs"]
        assert len(pairs) == 30

    def test_every_pair_resolves_to_a_real_trigger_and_merchant(self):
        pairs = load_json(EXPANDED_DIR / "test_pairs.json")["pairs"]
        trigger_ids = {f.stem for f in (EXPANDED_DIR / "triggers").glob("*.json")}
        merchant_ids = {f.stem for f in (EXPANDED_DIR / "merchants").glob("*.json")}

        for pair in pairs:
            assert pair["trigger_id"] in trigger_ids, f"Missing trigger file for {pair['trigger_id']}"
            assert pair["merchant_id"] in merchant_ids, f"Missing merchant file for {pair['merchant_id']}"
            if pair.get("customer_id"):
                customer_path = EXPANDED_DIR / "customers" / f"{pair['customer_id']}.json"
                assert customer_path.exists(), f"Missing customer file for {pair['customer_id']}"

    async def test_bot_produces_an_action_for_every_canonical_pair(self, app_client):
        """
        For all 30 canonical test pairs: push the required contexts, tick,
        and confirm the bot returns a well-formed action (LLM mocked for
        determinism/offline execution).
        """
        client, app = app_client
        pairs = load_json(EXPANDED_DIR / "test_pairs.json")["pairs"]

        pushed_categories = set()
        pushed_merchants = set()
        pushed_customers = set()

        for pair in pairs:
            merchant_payload = load_json(EXPANDED_DIR / "merchants" / f"{pair['merchant_id']}.json")
            category_slug = merchant_payload["category_slug"]

            if category_slug not in pushed_categories:
                category_payload = load_json(EXPANDED_DIR / "categories" / f"{category_slug}.json")
                await client.post("/v1/context", json={
                    "scope": "category", "context_id": category_slug, "version": 1,
                    "payload": category_payload, "delivered_at": "2026-04-26T09:45:00Z",
                })
                pushed_categories.add(category_slug)

            if pair["merchant_id"] not in pushed_merchants:
                await client.post("/v1/context", json={
                    "scope": "merchant", "context_id": pair["merchant_id"], "version": 1,
                    "payload": merchant_payload, "delivered_at": "2026-04-26T09:46:00Z",
                })
                pushed_merchants.add(pair["merchant_id"])

            if pair.get("customer_id") and pair["customer_id"] not in pushed_customers:
                customer_path = EXPANDED_DIR / "customers" / f"{pair['customer_id']}.json"
                if customer_path.exists():
                    customer_payload = load_json(customer_path)
                    await client.post("/v1/context", json={
                        "scope": "customer", "context_id": pair["customer_id"], "version": 1,
                        "payload": customer_payload, "delivered_at": "2026-04-26T09:46:30Z",
                    })
                    pushed_customers.add(pair["customer_id"])

            trigger_payload = load_json(EXPANDED_DIR / "triggers" / f"{pair['trigger_id']}.json")
            await client.post("/v1/context", json={
                "scope": "trigger", "context_id": pair["trigger_id"], "version": 1,
                "payload": trigger_payload, "delivered_at": "2026-04-26T09:47:00Z",
            })

        mock_llm_response = {
            "body": "Test composed message with a concrete number: 42% improvement.",
            "cta": "open_ended", "send_as": "nexora",
            "template_params": ["param1"], "rationale": "Test rationale referencing the trigger.",
        }

        results = []
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_llm_response)):
            for pair in pairs:
                trigger_payload = load_json(EXPANDED_DIR / "triggers" / f"{pair['trigger_id']}.json")
                expires = trigger_payload.get("expires_at", "2026-12-31T23:59:59Z")
                # Use a now safely before this trigger's own expiry so we're
                # testing composition, not accidentally testing expiry-skip.
                from datetime import datetime, timedelta
                try:
                    expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    now_iso = (expires_dt - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
                except ValueError:
                    now_iso = "2026-04-26T10:35:00Z"

                resp = await client.post("/v1/tick", json={
                    "now": now_iso,
                    "available_triggers": [pair["trigger_id"]],
                })
                assert resp.status_code == 200
                actions = resp.json()["actions"]
                results.append((pair["test_id"], len(actions)))

        produced = sum(1 for _, n in results if n == 1)
        # Every pair should produce exactly one action given valid context +
        # a non-expired trigger + a mocked LLM that always returns a valid
        # composition. If any pair fails, print which ones for diagnosis.
        failed = [(tid, n) for tid, n in results if n != 1]
        assert not failed, f"Pairs that did not produce exactly 1 action: {failed}"
        assert produced == 30
