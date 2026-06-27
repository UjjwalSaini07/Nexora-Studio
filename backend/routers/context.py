# backend/routers/context.py
"""
POST /v1/context — push category/merchant/customer/trigger data.

Idempotency contract:
- version == current_version  -> reject as stale_version (no-op write, but
  the harness may legitimately re-send the same version; we still report
  accepted=False with current_version so it can tell the difference between
  "rejected because stale" and "rejected because malformed").
- version <  current_version  -> reject as stale_version
- version >  current_version  -> accept, persist, bump version atomically
- never seen before (-1)      -> accept, persist, increment scope counter
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_redis, get_mongo, verify_auth
from models.requests import ContextBody, ContextAckResponse, VALID_SCOPES
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from config import CONTEXT_PAYLOAD_SIZE_CAP_KB
from logging_config import get_logger
import json

logger = get_logger("nexora.routers.context")

router = APIRouter()


@router.post("/v1/context", response_model=ContextAckResponse, dependencies=[Depends(verify_auth)])
async def push_context(
    body: ContextBody,
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    if body.scope not in VALID_SCOPES:
        raise HTTPException(
            status_code=400,
            detail={"accepted": False, "reason": "invalid_scope", "details": f"scope must be one of {sorted(VALID_SCOPES)}"},
        )

    payload_size_kb = len(json.dumps(body.payload).encode("utf-8")) / 1024
    if payload_size_kb > CONTEXT_PAYLOAD_SIZE_CAP_KB:
        raise HTTPException(
            status_code=413,
            detail={
                "accepted": False,
                "reason": "payload_too_large",
                "details": f"payload is {payload_size_kb:.1f}KB, cap is {CONTEXT_PAYLOAD_SIZE_CAP_KB}KB",
            },
        )

    current_version = await redis.get_context_version(body.scope, body.context_id)

    # Idempotent: same version (or older) is rejected as stale.
    if current_version != -1 and body.version <= current_version:
        return ContextAckResponse(
            accepted=False,
            reason="stale_version",
            current_version=current_version,
        )

    is_first_time = current_version == -1

    # Persist to Mongo first (system of record), then flip the Redis version
    # pointer — if Mongo write fails we raise before any version state changes.
    await mongo.upsert_context(
        scope=body.scope,
        context_id=body.context_id,
        version=body.version,
        payload=body.payload,
        delivered_at=body.delivered_at,
    )

    if is_first_time:
        await redis.set_context_version_if_new(body.scope, body.context_id, body.version)
    else:
        await redis.set_context_version(body.scope, body.context_id, body.version)

    stored_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ack_id = f"ack_{body.context_id}_v{body.version}"

    logger.info(
        "Context accepted",
        extra={"ctx": {"scope": body.scope, "context_id": body.context_id, "version": body.version}},
    )

    return ContextAckResponse(accepted=True, ack_id=ack_id, stored_at=stored_at)
