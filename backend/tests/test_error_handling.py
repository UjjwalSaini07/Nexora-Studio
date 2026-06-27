# backend/tests/test_error_handling.py
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))


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
            self.db = self.client["nexora_test_errors"]
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

    import fakeredis.aioredis
    import mongomock_motor

    app = main_module.app
    app.state.redis = FakeRedisStore()
    app.state.mongo = FakeMongoStore()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, app

    await app.state.redis.close()


@pytest.mark.asyncio
async def test_malformed_json_returns_http_400(app_client):
    """
    Sending malformed JSON syntax should return HTTP 400 with INVALID_JSON code.
    """
    client, _ = app_client
    resp = await client.post(
        "/v1/tick",
        content="{'now': '2026-04-26T10:00:00Z',",  # Invalid JSON syntax
        headers={"content-type": "application/json"}
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_JSON"
    assert "malformed JSON" in data["error"]["message"]


@pytest.mark.asyncio
async def test_nonexistent_trigger_returns_http_404(app_client):
    """
    Referencing a trigger that does not exist in MongoDB should return HTTP 404 with TRIGGER_NOT_FOUND.
    """
    client, _ = app_client
    resp = await client.post(
        "/v1/tick",
        json={
            "now": "2026-04-26T10:00:00Z",
            "available_triggers": ["trg_nonexistent_id"]
        }
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "TRIGGER_NOT_FOUND"
    assert "trg_nonexistent_id" in data["error"]["message"]


@pytest.mark.asyncio
async def test_nonexistent_merchant_in_reply_returns_http_404(app_client):
    """
    Providing a merchant_id that doesn't exist in MongoDB should return HTTP 404 with MERCHANT_NOT_FOUND.
    """
    client, _ = app_client
    resp = await client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_test",
            "merchant_id": "m_nonexistent",
            "from_role": "merchant",
            "message": "Hello",
            "received_at": "2026-04-26T10:00:00Z",
            "turn_number": 1
        }
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "MERCHANT_NOT_FOUND"


@pytest.mark.asyncio
async def test_nonexistent_customer_in_reply_returns_http_404(app_client):
    """
    Providing a customer_id that doesn't exist in MongoDB should return HTTP 404 with CUSTOMER_NOT_FOUND.
    """
    client, _ = app_client
    resp = await client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_test",
            "customer_id": "c_nonexistent",
            "from_role": "customer",
            "message": "Hello",
            "received_at": "2026-04-26T10:00:00Z",
            "turn_number": 1
        }
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "CUSTOMER_NOT_FOUND"


@pytest.mark.asyncio
async def test_blank_conversation_id_returns_http_422(app_client):
    """
    Whitespace or empty conversation_id should return HTTP 422 with VALIDATION_ERROR.
    """
    client, _ = app_client
    resp = await client.post(
        "/v1/reply",
        json={
            "conversation_id": "   ",
            "from_role": "merchant",
            "message": "Hello",
            "received_at": "2026-04-26T10:00:00Z",
            "turn_number": 1
        }
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_invalid_timestamp_returns_http_422(app_client):
    """
    Invalid timestamp format should fail validation (HTTP 422).
    """
    client, _ = app_client
    resp = await client.post(
        "/v1/tick",
        json={
            "now": "not-a-timestamp",
            "available_triggers": []
        }
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_oversized_payload_returns_http_413(app_client):
    """
    Request bodies exceeding 2MB should be rejected with HTTP 413.
    """
    client, _ = app_client
    huge_body = "x" * (2 * 1024 * 1024 + 100)
    resp = await client.post(
        "/v1/tick",
        content=huge_body,
        headers={"content-type": "application/json"}
    )
    assert resp.status_code == 413
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_unsupported_method_returns_http_405(app_client):
    """
    Requesting an unsupported HTTP method (e.g. GET on /v1/tick) should return HTTP 405 with METHOD_NOT_ALLOWED.
    """
    client, _ = app_client
    resp = await client.get("/v1/tick")
    assert resp.status_code == 405
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "METHOD_NOT_ALLOWED"
