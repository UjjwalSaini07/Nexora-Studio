import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from composer.engine import EngagementComposer
from reply.handler import ReplyHandler
from models.context import TriggerContext, MerchantContext, CategoryContext


class TestWaitEnforcement:
    @pytest.mark.asyncio
    async def test_wait_state_respected_in_composer(self, redis_store, mongo_store):
        """Verify that if a conversation has an active wait_until timestamp,
        compose_for_trigger returns None, unless the trigger has urgency >= 5."""
        with patch("composer.engine.DEMO_MODE", False):
            composer = EngagementComposer(redis_store, mongo_store)

            # 1. Setup mock contexts in mongo
            trigger_id = "trg_wait_test"
            await mongo_store.upsert_context("trigger", trigger_id, 1, {
                "id": trigger_id,
                "scope": "merchant",
                "kind": "research_digest",
                "source": "internal",
                "merchant_id": "m_wait_001",
                "payload": {},
                "urgency": 3,
                "suppression_key": "sup_wait_test",
            }, "2026-06-25T10:00:00Z")

            await mongo_store.upsert_context("category", "dentists", 1, {
                "slug": "dentists",
                "voice": {"tone": "clinical_peer"},
                "peer_stats": {"avg_ctr": 0.03},
            }, "2026-06-25T10:00:00Z")

            await mongo_store.upsert_context("merchant", "m_wait_001", 1, {
                "merchant_id": "m_wait_001",
                "category_slug": "dentists",
                "identity": {"name": "Test Clinic", "languages": ["en"]},
            }, "2026-06-25T10:00:00Z")

            # Set wait state in redis until 2026-06-25T14:00:00Z
            conv_id = "conv_m_wait_001_research_digest"
            await redis_store.set_conversation_wait(conv_id, "2026-06-25T14:00:00Z")

            # Case A: now is BEFORE wait expiration -> trigger is skipped (returns None)
            res_skipped = await composer.compose_for_trigger(trigger_id, "2026-06-25T12:00:00Z")
            assert res_skipped is None

            # Case B: now is AFTER wait expiration -> trigger is processed (hits LLM)
            mock_response = {
                "body": "Hi Doc, your CTR has dropped. Let's fix this now.",
                "cta": "open_ended",
                "send_as": "nexora",
                "template_params": [],
                "rationale": "x",
            }
            with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
                res_processed = await composer.compose_for_trigger(trigger_id, "2026-06-25T15:00:00Z")
                assert res_processed is not None
                assert res_processed["trigger_id"] == trigger_id

            # Case C: urgent trigger (urgency=5) bypasses active wait state
            await mongo_store.upsert_context("trigger", "trg_wait_urgent", 1, {
                "id": "trg_wait_urgent",
                "scope": "merchant",
                "kind": "research_digest",
                "source": "internal",
                "merchant_id": "m_wait_001",
                "payload": {},
                "urgency": 5,
                "suppression_key": "sup_wait_urgent",
            }, "2026-06-25T10:00:00Z")

            mock_response_urgent = {
                "body": "Hi Doc, urgent update about your peer ratings now.",
                "cta": "open_ended",
                "send_as": "nexora",
                "template_params": [],
                "rationale": "x",
            }

            # Suppression key is not active, wait is active, but urgency is 5 -> should bypass wait
            with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response_urgent)):
                res_urgent = await composer.compose_for_trigger("trg_wait_urgent", "2026-06-25T12:00:00Z")
                assert res_urgent is not None
                assert res_urgent["trigger_id"] == "trg_wait_urgent"


class TestReplyRateLimiter:
    def test_reply_rate_limiting_enforced(self):
        """Verify that POST /v1/reply rate limits trigger HTTP 429 after threshold."""
        import main as main_module
        from fastapi.testclient import TestClient

        client = TestClient(main_module.app)
        headers = {"X-Nexora-Auth": "test_auth_placeholder"}

        # Patch verify_auth to bypass if needed, or rely on auth dependency
        # We can also mock rate_limit_hit on redis to return False to simulate limit hit
        app = main_module.app
        original_redis = app.state.redis

        class MockRedisStoreLimitHit:
            async def rate_limit_hit(self, bucket_key: str, window_seconds: int, limit: int):
                # Always simulate limit hit
                return False, limit + 1

            async def get_context_counts(self):
                return {}

        app.state.redis = MockRedisStoreLimitHit()
        try:
            # Under mock limit hit, any call to /v1/reply should return HTTP 429
            resp = client.post("/v1/reply", headers=headers, json={
                "conversation_id": "conv_ratelimit_test",
                "merchant_id": "m_001",
                "from_role": "merchant",
                "message": "Hi",
                "received_at": "2026-06-25T10:00:00Z",
                "turn_number": 2,
            })
            assert resp.status_code == 429
            assert "Rate limit exceeded" in resp.json()["detail"]
        finally:
            app.state.redis = original_redis
