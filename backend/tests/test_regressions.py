# backend/tests/test_regressions.py
"""
Regression tests for two real bugs found via live end-to-end testing against
the official dataset (not caught by earlier unit-level mocks):

1. EngagementComposer.compose_for_trigger used datetime.now(timezone.utc) —
   the REAL wall-clock time — for its expiry check, instead of the `now_iso`
   simulated-time parameter passed in from the judge's /v1/tick request.
   Since the seed dataset's trigger `expires_at` values are authored
   relative to the challenge's own simulated timeline, this silently
   suppressed every trigger once real time moved past that timeline,
   even when the trigger was still "live" from the judge's point of view.

2. /v1/healthz crashed with a raw 500 if Redis was unreachable, instead of
   returning status="degraded" with redis_connected=False. A liveness
   probe that crashes on a backend hiccup is worse than useless.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from composer.engine import EngagementComposer
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore


class TestSimulatedTimeExpiryRegression:
    """compose_for_trigger must use now_iso (simulated time), never real wall-clock time."""

    async def test_trigger_not_suppressed_when_now_iso_is_before_expiry(self, redis_store, mongo_store):
        """
        Even if the REAL current date is long past the trigger's expires_at
        (as it always will be for this dataset, eventually), the trigger
        must still compose normally as long as the *simulated* `now_iso`
        passed into compose_for_trigger is before expires_at.
        """
        merchant_id = "m_regression_001"
        category_slug = "dentists"

        await mongo_store.upsert_context("category", category_slug, 1, {
            "slug": category_slug,
            "voice": {"tone": "clinical_peer", "register": "professional", "code_mix": "en"},
            "peer_stats": {"avg_ctr": 0.03},
        }, "2026-01-01T00:00:00Z")

        await mongo_store.upsert_context("merchant", merchant_id, 1, {
            "merchant_id": merchant_id,
            "category_slug": category_slug,
            "identity": {"name": "Test Clinic", "owner_first_name": "Test", "languages": ["en"]},
        }, "2026-01-01T00:00:00Z")

        trigger_id = "trg_regression_001"
        # expires_at deliberately set in what is, by the time this test
        # suite runs, the PAST relative to real wall-clock time — but still
        # "in the future" relative to the simulated `now_iso` we'll pass.
        await mongo_store.upsert_context("trigger", trigger_id, 1, {
            "id": trigger_id,
            "scope": "merchant",
            "kind": "research_digest",
            "source": "external",
            "merchant_id": merchant_id,
            "payload": {},
            "suppression_key": "sup_regression_001",
            "expires_at": "2026-05-03T00:00:00Z",  # in the past relative to real "today"
        }, "2026-01-01T00:00:00Z")

        composer = EngagementComposer(redis_store, mongo_store)

        mock_response = {
            "body": "Test message with concrete content.",
            "cta": "open_ended", "send_as": "vera",
            "template_params": [], "rationale": "x",
        }
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
            # now_iso is BEFORE the trigger's expires_at on the SIMULATED
            # timeline, even though real wall-clock time has long since
            # passed expires_at.
            result = await composer.compose_for_trigger(trigger_id, "2026-04-26T10:35:00Z")

        assert result is not None, (
            "Trigger was incorrectly suppressed — compose_for_trigger must "
            "compare expires_at against the simulated now_iso parameter, "
            "not the real wall-clock time."
        )
        assert result["trigger_id"] == trigger_id

    async def test_trigger_suppressed_when_now_iso_is_after_expiry(self, redis_store, mongo_store):
        """Sanity check the other direction: a trigger IS correctly skipped
        when the simulated now_iso is genuinely past its expires_at."""
        merchant_id = "m_regression_002"
        category_slug = "dentists"

        await mongo_store.upsert_context("category", category_slug, 1, {
            "slug": category_slug,
            "voice": {"tone": "clinical_peer", "register": "professional", "code_mix": "en"},
            "peer_stats": {"avg_ctr": 0.03},
        }, "2026-01-01T00:00:00Z")

        await mongo_store.upsert_context("merchant", merchant_id, 1, {
            "merchant_id": merchant_id,
            "category_slug": category_slug,
            "identity": {"name": "Test Clinic 2", "owner_first_name": "Test", "languages": ["en"]},
        }, "2026-01-01T00:00:00Z")

        trigger_id = "trg_regression_002"
        await mongo_store.upsert_context("trigger", trigger_id, 1, {
            "id": trigger_id,
            "scope": "merchant",
            "kind": "research_digest",
            "source": "external",
            "merchant_id": merchant_id,
            "payload": {},
            "suppression_key": "sup_regression_002",
            "expires_at": "2026-05-03T00:00:00Z",
        }, "2026-01-01T00:00:00Z")

        composer = EngagementComposer(redis_store, mongo_store)
        mock_response = {"body": "x", "cta": "open_ended", "send_as": "vera", "template_params": [], "rationale": "x"}
        with patch("composer.llm_client.LLMClient.complete", new=AsyncMock(return_value=mock_response)):
            result = await composer.compose_for_trigger(trigger_id, "2026-06-01T00:00:00Z")  # after expiry

        assert result is None


class TestHealthzResilienceRegression:
    """/v1/healthz must report status=degraded, never crash, if a datastore is unreachable."""

    async def test_healthz_survives_redis_ping_exception(self, mongo_store):
        from routers.healthz import healthz

        class BrokenRedisStore:
            async def ping(self):
                raise ConnectionError("simulated redis outage")

            async def get_context_counts(self):
                raise ConnectionError("simulated redis outage")

        result = await healthz(redis=BrokenRedisStore(), mongo=mongo_store)
        assert result.status == "degraded"
        assert result.redis_connected is False
        assert result.contexts_loaded == {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}

    async def test_healthz_survives_mongo_ping_exception(self, redis_store):
        from routers.healthz import healthz

        class BrokenMongoStore:
            async def ping(self):
                raise ConnectionError("simulated mongo outage")

        result = await healthz(redis=redis_store, mongo=BrokenMongoStore())
        assert result.status == "degraded"
        assert result.mongo_connected is False

    async def test_healthz_ok_when_both_stores_healthy(self, redis_store, mongo_store):
        from routers.healthz import healthz

        result = await healthz(redis=redis_store, mongo=mongo_store)
        assert result.status == "ok"
        assert result.redis_connected is True
        assert result.mongo_connected is True
