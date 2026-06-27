# backend/routers/explain.py
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_redis, get_mongo, verify_auth
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from composer.output_validator import _detect_levers

router = APIRouter()


@router.get("/v1/action/{conversation_id}/explain", dependencies=[Depends(verify_auth)])
async def explain_action(
    conversation_id: str,
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    # 1. Fetch the latest action log for the conversation_id
    action_doc = await mongo.actions_log.find_one(
        {"conversation_id": conversation_id},
        sort=[("logged_at", -1)]
    )
    if not action_doc:
        raise HTTPException(
            status_code=404,
            detail={"success": False, "message": f"No action logs found for conversation_id: {conversation_id}"}
        )

    trigger_id = action_doc.get("trigger_id")
    merchant_id = action_doc.get("merchant_id")
    customer_id = action_doc.get("customer_id")
    category_slug = action_doc.get("category")

    # 2. Fetch context documents from Mongo
    trigger_doc = await mongo.get_context("trigger", trigger_id) if trigger_id else None
    merchant_doc = await mongo.get_context("merchant", merchant_id) if merchant_id else None
    
    if not category_slug and merchant_doc:
        category_slug = merchant_doc.get("payload", {}).get("category_slug")
    category_doc = await mongo.get_context("category", category_slug) if category_slug else None
    customer_doc = await mongo.get_context("customer", customer_id) if customer_id else None

    # 3. Signals extraction
    merchant_signals = merchant_doc.get("payload", {}).get("signals", []) if merchant_doc else []
    
    category_signals = []
    if category_doc:
        payload = category_doc.get("payload", {})
        category_signals.extend([b.get("note") for b in payload.get("seasonal_beats", []) if b.get("note")])
        category_signals.extend([t.get("query") for t in payload.get("trend_signals", []) if t.get("query")])
        
    customer_signals = []
    if customer_doc:
        c_payload = customer_doc.get("payload", {})
        state = c_payload.get("state")
        if state:
            customer_signals.append(f"state:{state}")
        pref_slots = c_payload.get("preferences", {}).get("preferred_slots")
        if pref_slots:
            customer_signals.append(f"preferred_slots:{pref_slots}")
        age_band = c_payload.get("identity", {}).get("age_band")
        if age_band:
            customer_signals.append(f"age_band:{age_band}")

    # 4. Levers detection
    compulsion_levers_used = _detect_levers(action_doc.get("body", ""))

    # 5. Redis checks
    suppression_key = action_doc.get("suppression_key")
    is_suppressed = False
    if suppression_key:
        is_suppressed = await redis.is_suppressed(suppression_key)

    wait_until = await redis.get_conversation_wait(conversation_id)
    is_waiting = False
    if wait_until:
        try:
            wait_until_dt = datetime.fromisoformat(wait_until.replace("Z", "+00:00"))
            is_waiting = datetime.now(timezone.utc) < wait_until_dt
        except Exception:
            pass

    priority_score = action_doc.get("priority_score", 0)
    priority_rank = action_doc.get("priority_rank", 0)
    priority_reason = action_doc.get("priority_reason", "")
    trigger_kind = action_doc.get("trigger", "")

    urgency = action_doc.get("urgency")
    if urgency is None and trigger_doc:
        urgency = trigger_doc.get("payload", {}).get("urgency")
    if urgency is None:
        urgency = 3

    return {
        "conversation_id": conversation_id,
        "trigger_id": trigger_id,
        "why_selected": f"Trigger '{trigger_id}' of kind '{trigger_kind}' with urgency {urgency} was selected and assigned a priority score of {priority_score} (ranked #{priority_rank}).",
        "priority_breakdown": {
            "score": priority_score,
            "rank": priority_rank,
            "reason": priority_reason
        },
        "merchant_signals_used": merchant_signals,
        "category_signals_used": category_signals,
        "customer_signals_used": customer_signals,
        "compulsion_levers_used": compulsion_levers_used,
        "confidence_score": action_doc.get("confidence", 0.0),
        "suppression_status": {
            "is_suppressed": is_suppressed,
            "suppression_key": suppression_key
        },
        "wait_state_status": {
            "is_waiting": is_waiting,
            "wait_until": wait_until
        },
        "rationale": action_doc.get("rationale", ""),
        "trigger_ranking_details": {
            "score": priority_score,
            "rank": priority_rank,
            "reason": priority_reason
        }
    }
