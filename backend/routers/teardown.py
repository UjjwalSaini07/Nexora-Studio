"""
POST /v1/teardown (optional, per challenge-testing-brief.md §11) —
magicpin's judge harness may call this at the end of a test window. On
receiving it, the bot must wipe all persisted context/conversation state
rather than retaining it after the test ends.

This is intentionally a no-auth-required, idempotent, always-200 endpoint:
even if called multiple times or with no body, it should just wipe
whatever is there and report what was removed.
"""
from fastapi import APIRouter, Depends

from dependencies import get_redis, get_mongo
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from logging_config import get_logger

logger = get_logger("nexora.routers.teardown")

router = APIRouter()


@router.post("/v1/teardown")
async def teardown(
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    redis_deleted = 0
    mongo_deleted = {}

    try:
        from dataset.demo_generator import reset_demo_data_ensured
        reset_demo_data_ensured()
    except Exception as exc:
        logger.error("Failed to reset demo data state during teardown", extra={"ctx": {"error": str(exc)}})


    try:
        redis_deleted = await redis.wipe_all_nexora_keys()
    except Exception as exc:
        logger.error("Failed to wipe Redis state during teardown", extra={"ctx": {"error": str(exc)}})

    try:
        mongo_deleted = await mongo.wipe_all()
    except Exception as exc:
        logger.error("Failed to wipe Mongo state during teardown", extra={"ctx": {"error": str(exc)}})

    logger.info(
        "Teardown completed — all context and conversation state wiped",
        extra={"ctx": {"redis_keys_deleted": redis_deleted, "mongo_deleted": mongo_deleted}},
    )

    return {
        "status": "wiped",
        "redis_keys_deleted": redis_deleted,
        "mongo_documents_deleted": mongo_deleted,
    }
