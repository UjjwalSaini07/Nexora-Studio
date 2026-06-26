# backend/routers/reply.py
import asyncio

from fastapi import APIRouter, Depends

from dependencies import get_redis, get_mongo, verify_auth
from models.requests import ReplyBody, ReplyResponse
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from reply.handler import ReplyHandler
from config import REPLY_TIMEOUT_SECONDS
from logging_config import get_logger

logger = get_logger("vera.routers.reply")

router = APIRouter()


@router.post("/v1/reply", response_model=ReplyResponse, dependencies=[Depends(verify_auth)])
async def handle_reply(
    body: ReplyBody,
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
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
