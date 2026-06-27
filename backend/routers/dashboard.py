# backend/routers/dashboard.py
"""
Read-only endpoints that exist solely to back the Next.js operations
dashboard (Part 5 of the spec): live context inspector, recent
actions/replies feed, and basic score-analytics placeholders.

These are NOT part of the 5 judge-facing endpoints and are namespaced under
/v1/dashboard/* to make that distinction unambiguous. They are safe to
disable in production by not mounting frontend traffic to this bot's
public URL (the dashboard should talk to its own deployment or be proxied
internally) — but they carry no sensitive data beyond what's already in
context payloads.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from dependencies import get_redis, get_mongo
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore

router = APIRouter(prefix="/v1/dashboard")


@router.get("/contexts")
async def list_contexts(
    scope: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    mongo: MongoStore = Depends(get_mongo),
):
    contexts = await mongo.list_contexts(scope=scope, limit=limit)
    return {"contexts": contexts, "count": len(contexts)}


@router.get("/contexts/{scope}/{context_id}")
async def get_context_detail(
    scope: str,
    context_id: str,
    mongo: MongoStore = Depends(get_mongo),
):
    doc = await mongo.get_context(scope, context_id)
    return {"context": doc}


@router.get("/actions")
async def recent_actions(
    limit: int = Query(default=50, le=200),
    mongo: MongoStore = Depends(get_mongo),
):
    actions = await mongo.get_recent_actions(limit=limit)
    return {"actions": actions, "count": len(actions)}


@router.get("/replies")
async def recent_replies(
    limit: int = Query(default=50, le=200),
    mongo: MongoStore = Depends(get_mongo),
):
    replies = await mongo.get_recent_replies(limit=limit)
    return {"replies": replies, "count": len(replies)}


@router.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str,
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    turns = await redis.get_conversation(conversation_id)
    sent = await redis.get_sent_messages(conversation_id)
    ended = await redis.is_conversation_ended(conversation_id)
    auto_reply_count = await redis.get_auto_reply_count(conversation_id)
    replies_log = await mongo.get_replies_for_conversation(conversation_id)
    return {
        "conversation_id": conversation_id,
        "turns": turns,
        "sent_by_nexora": sent,
        "ended": ended,
        "auto_reply_count": auto_reply_count,
        "replies_log": replies_log,
    }


@router.get("/stats")
async def stats(
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    counts = await redis.get_context_counts()
    recent_actions_list = await mongo.get_recent_actions(limit=200)

    trigger_kind_counts: dict[str, int] = {}
    cta_counts: dict[str, int] = {}
    for a in recent_actions_list:
        # template_name correlates 1:1 with trigger kind via TEMPLATE_NAME_MAP
        tname = a.get("template_name", "unknown")
        trigger_kind_counts[tname] = trigger_kind_counts.get(tname, 0) + 1
        cta = a.get("cta", "unknown")
        cta_counts[cta] = cta_counts.get(cta, 0) + 1

    return {
        "contexts_loaded": counts,
        "total_actions_logged": len(recent_actions_list),
        "actions_by_template": trigger_kind_counts,
        "actions_by_cta": cta_counts,
    }
