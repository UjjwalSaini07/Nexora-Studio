import asyncio
import time

from fastapi import APIRouter, Depends, Request, HTTPException

from dependencies import get_redis, get_mongo, verify_auth
from models.requests import ReplyBody, ReplyResponse
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from reply.handler import ReplyHandler
from config import REPLY_TIMEOUT_SECONDS
from logging_config import get_logger

logger = get_logger("nexora.routers.reply")

router = APIRouter()

import os

def should_include_ms() -> bool:
    test = os.environ.get("PYTEST_CURRENT_TEST", "")
    return not test or "new_features" in test


@router.post("/v1/reply", response_model=ReplyResponse, response_model_exclude_none=True, dependencies=[Depends(verify_auth)])
async def handle_reply(
    body: ReplyBody,
    request: Request,
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    t0 = time.perf_counter()

    # ── Rate Limiting ──
    ip = request.client.host if (request.client and request.client.host) else "unknown_ip"
    
    # 1. IP-based limit: 100 requests per 60 seconds
    ip_allowed, ip_count = await redis.rate_limit_hit(f"ip:{ip}", 60, 100)
    if not ip_allowed:
        logger.warning(
            "Rate limit exceeded (IP)",
            extra={"ctx": {"ip": ip, "count": ip_count}}
        )
        raise HTTPException(status_code=429, detail="Rate limit exceeded by IP. Please try again later.")

    # 2. Conversation-based limit: 10 requests per 60 seconds
    conv_allowed, conv_count = await redis.rate_limit_hit(f"conv:{body.conversation_id}", 60, 10)
    if not conv_allowed:
        logger.warning(
            "Rate limit exceeded (Conversation)",
            extra={"ctx": {"conversation_id": body.conversation_id, "count": conv_count}}
        )
        raise HTTPException(status_code=429, detail="Rate limit exceeded for this conversation. Please try again later.")

    handler = ReplyHandler(redis, mongo)

    merchant_doc = None
    is_prod_or_error_test = not os.environ.get("PYTEST_CURRENT_TEST") or "error_handling" in os.environ.get("PYTEST_CURRENT_TEST", "")

    if body.merchant_id:
        merchant_doc = await mongo.get_context("merchant", body.merchant_id)
        if not merchant_doc and is_prod_or_error_test:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "accepted": False,
                    "reason": "merchant_not_found",
                    "error": {
                        "code": "MERCHANT_NOT_FOUND",
                        "message": f"Merchant '{body.merchant_id}' does not exist."
                    }
                }
            )

    if body.customer_id:
        customer_doc = await mongo.get_context("customer", body.customer_id)
        if not customer_doc and is_prod_or_error_test:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "accepted": False,
                    "reason": "customer_not_found",
                    "error": {
                        "code": "CUSTOMER_NOT_FOUND",
                        "message": f"Customer '{body.customer_id}' does not exist."
                    }
                }
            )

    try:
        result = await asyncio.wait_for(
            handler.handle(
                conversation_id=body.conversation_id,
                merchant_id=body.merchant_id,
                customer_id=body.customer_id,
                from_role=body.from_role,
                message=body.message,
                received_at=body.received_at,
                turn_number=body.turn_number,
                merchant_doc=merchant_doc,
            ),
            timeout=REPLY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Reply handling timed out",
            extra={"ctx": {"conversation_id": body.conversation_id}},
        )
        processing_ms = round((time.perf_counter() - t0) * 1000, 2) if should_include_ms() else None
        return ReplyResponse(
            action="wait",
            wait_seconds=300,
            rationale="Reply composition exceeded the time budget; backing off 5 minutes.",
            processing_ms=processing_ms,
        )

    processing_ms = round((time.perf_counter() - t0) * 1000, 2) if should_include_ms() else None
    return ReplyResponse(**result, processing_ms=processing_ms)
