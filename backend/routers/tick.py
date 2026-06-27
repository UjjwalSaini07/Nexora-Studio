# backend/routers/tick.py
import asyncio

from fastapi import APIRouter, Depends

from dependencies import get_redis, get_mongo, verify_auth
from models.requests import TickBody, TickResponse
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from composer.engine import EngagementComposer
from config import TICK_MAX_ACTIONS, TICK_TIMEOUT_SECONDS
from logging_config import get_logger

logger = get_logger("nexora.routers.tick")

router = APIRouter()


@router.post("/v1/tick", response_model=TickResponse, dependencies=[Depends(verify_auth)])
async def tick(
    body: TickBody,
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    composer = EngagementComposer(redis, mongo)
    actions = []

    triggers_to_process = body.available_triggers[:TICK_MAX_ACTIONS]

    tasks = [
        composer.compose_for_trigger(trg_id, body.now)
        for trg_id in triggers_to_process
    ]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=TICK_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Tick processing timed out before all triggers finished",
            extra={"ctx": {"trigger_count": len(triggers_to_process)}},
        )
        return TickResponse(actions=[])

    seen_pairs = set()
    for trg_id, result in zip(triggers_to_process, results):
        if isinstance(result, Exception):
            logger.error(
                "Trigger composition raised an exception",
                extra={"ctx": {"trigger_id": trg_id, "error": str(result)}},
            )
            continue
        if not result:
            continue

        # Per challenge-testing-brief.md FAQ: only one action per
        # (merchant_id, conversation_id) pair is allowed per tick. If two
        # triggers in this batch resolved to the same pair (e.g. a retried
        # or duplicate trigger_id targeting the same conversation), keep
        # only the first and skip the rest — a follow-up tick can send more.
        pair_key = (result.get("merchant_id"), result.get("conversation_id"))
        if pair_key in seen_pairs:
            logger.warning(
                "Skipping duplicate action for (merchant_id, conversation_id) pair in same tick",
                extra={"ctx": {"trigger_id": trg_id, "pair_key": pair_key}},
            )
            continue
        seen_pairs.add(pair_key)

        actions.append(result)
        try:
            await mongo.log_action(result)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to log action", extra={"ctx": {"error": str(exc)}})

    # Log tick execution metadata to MongoDB
    try:
        await mongo.log_tick({
            "now": body.now,
            "available_triggers": body.available_triggers,
            "actions": actions[:TICK_MAX_ACTIONS]
        })
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to log tick", extra={"ctx": {"error": str(exc)}})

    return TickResponse(actions=actions[:TICK_MAX_ACTIONS])
