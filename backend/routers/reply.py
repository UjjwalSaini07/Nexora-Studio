# backend/routers/reply.py
import asyncio

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


@router.post("/v1/reply", response_model=ReplyResponse, dependencies=[Depends(verify_auth)])
async def handle_reply(
    body: ReplyBody,
    request: Request,
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
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
    if body.merchant_id:
        merchant_doc = await mongo.get_context("merchant", body.merchant_id)

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
        return ReplyResponse(
            action="wait",
            wait_seconds=300,
            rationale="Reply composition exceeded the time budget; backing off 5 minutes.",
        )

    return ReplyResponse(**result)
