# backend/routers/tick.py
import asyncio

from fastapi import APIRouter, Depends

from dependencies import get_redis, get_mongo, verify_auth
from models.requests import TickBody, TickResponse
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from composer.engine import EngagementComposer
from composer.trigger_priority_engine import rank_triggers
from config import TICK_MAX_ACTIONS, TICK_TIMEOUT_SECONDS, DEMO_MODE
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

    raw_trigger_ids = body.available_triggers[:TICK_MAX_ACTIONS]

    # ── Step 1: Load all trigger docs concurrently for priority ranking ──
    trigger_docs_raw = await asyncio.gather(
        *[mongo.get_context("trigger", trg_id) for trg_id in raw_trigger_ids],
        return_exceptions=True,
    )

    # Build a map of trigger_id -> doc (skip any load failures)
    doc_map: dict[str, dict] = {}
    for trg_id, doc in zip(raw_trigger_ids, trigger_docs_raw):
        if isinstance(doc, Exception) or doc is None:
            logger.warning(
                "Could not load trigger doc for priority ranking — will skip",
                extra={"ctx": {"trigger_id": trg_id}},
            )
            continue
        doc_map[trg_id] = doc

    # ── Step 2: Priority-rank the loaded trigger docs ────────────────────
    # rank_triggers returns docs sorted by descending priority score with
    # _priority_score / _priority_reason / _priority_rank injected.
    ranked_docs = rank_triggers(list(doc_map.values()), body.now)

    # Preserve ranked order for processing; triggers that failed to load
    # are simply absent from ranked_docs and will not be processed.
    triggers_to_process = [
        doc.get("context_id", doc.get("payload", {}).get("id"))
        for doc in ranked_docs
    ]
    # Filter out any None context_ids that slipped through
    triggers_to_process = [t for t in triggers_to_process if t]

    logger.info(
        "Trigger priority ranking complete",
        extra={
            "ctx": {
                "requested": len(raw_trigger_ids),
                "ranked": len(triggers_to_process),
                "order": triggers_to_process,
                "scores": {
                    doc.get("context_id", ""): doc.get("_priority_score", 0)
                    for doc in ranked_docs
                },
            }
        },
    )

    # ── Step 3: Compose actions concurrently in ranked order ─────────────
    # Wrap each task in an individual timeout so that one slow LLM call
    # does not abort the other concurrent completions.
    async def _compose_with_timeout(trg_id: str):
        try:
            return await asyncio.wait_for(
                composer.compose_for_trigger(trg_id, body.now),
                timeout=max(1.0, TICK_TIMEOUT_SECONDS - 2.0),
            )
        except asyncio.TimeoutError:
            logger.error(
                "Trigger composition timed out",
                extra={"ctx": {"trigger_id": trg_id}},
            )
            return None
        except Exception as exc:
            logger.error(
                "Trigger composition raised an exception",
                extra={"ctx": {"trigger_id": trg_id, "error": str(exc)}},
            )
            return None

    tasks = [
        _compose_with_timeout(trg_id)
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

    # ── Step 4: Deduplicate and collect results ───────────────────────────
    seen_pairs = set()
    for trg_id, result, ranked_doc in zip(triggers_to_process, results, ranked_docs):
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
        if not DEMO_MODE and pair_key in seen_pairs:
            logger.warning(
                "Skipping duplicate action for (merchant_id, conversation_id) pair in same tick",
                extra={"ctx": {"trigger_id": trg_id, "pair_key": pair_key}},
            )
            continue
        seen_pairs.add(pair_key)

        # Enrich result with priority metadata for dashboard/logging
        result["priority_score"] = ranked_doc.get("_priority_score", 0)
        result["priority_rank"] = ranked_doc.get("_priority_rank", 0)
        result["priority_reason"] = ranked_doc.get("_priority_reason", "")

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
            "ranked_trigger_order": triggers_to_process,
            "actions": actions[:TICK_MAX_ACTIONS]
        })
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to log tick", extra={"ctx": {"error": str(exc)}})

    return TickResponse(actions=actions[:TICK_MAX_ACTIONS])
